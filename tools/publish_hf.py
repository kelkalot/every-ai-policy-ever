#!/usr/bin/env python3
"""Publish the register to Hugging Face: a dataset, a gated dataset of source documents, and a Space.

    python3 tools/publish_hf.py                     # build the three folders under dist/hf/ and stop
    python3 tools/publish_hf.py --push              # build and upload (creates the repos if needed)
    python3 tools/publish_hf.py --push --private    # upload as private repos, for a review before going public

Repos (change with --namespace and --name):
  datasets/<namespace>/<name>           records, topics, related links and the source-file manifest as Parquet,
                                        the full JSON, the method (AGENTS.md) and the quality reports
  datasets/<namespace>/<name>-archive   the stored copies of official sources; gated, so a free account is needed
  spaces/<namespace>/<name>             the web app as a static Space

Copies of third-party pages (law firms, newspapers, NGOs, think tanks) are kept out of the archive dataset;
their URLs and hashes stay in the manifest. Edit THIRD_PARTY_HOSTS when new secondary sources are added.

Some official pages embed live access tokens in their scripts (for example a commenting service's
administrator token). The local archive keeps the exact copy; in the published copy each unexpired token is
replaced with REDACTED-ACCESS-TOKEN, and the manifest records both hashes (`sha256` = original,
`published_sha256` = published file). --squash-archive rewrites the archive dataset's history into one commit,
so that earlier revisions holding a token are no longer reachable.

Releases (README section 9): `--release` publishes the current main branch as version meta.version.
It first checks that main is clean and pushed, that the version is higher than the published one and not
yet tagged, that every record published before is still there, that the history and the stored files are
intact, that the built archive holds no live access tokens, and that the token can write. Only then does it
upload, add a "Changes in this version" section built from the new history events, and tag the version
on the three repositories and on GitHub. `--release --dry-run` runs every check and uploads nothing.

Needs: huggingface_hub and pyarrow (pip install huggingface_hub pyarrow), and `hf auth login`.
"""
import argparse
import base64
import csv
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from archive import ROLE_LABELS  # noqa: E402
import history  # noqa: E402
import validate  # noqa: E402

ROOT = build.ROOT
AUTHORS = build.AUTHORS
AFFILIATION = "AI Safety Department, SimulaMet & OsloMet"
MAINTAINERS = [("Michael A. Riegler", "michael@simula.no"), ("Sushant Gautam", "sushant@simula.no")]
CONTACT = "%s, %s" % (" and ".join("%s (%s)" % m for m in MAINTAINERS), AFFILIATION)
PRETTY_NAME = build.NAME
# copies that macOS or iCloud make when a file changes on two sides, such as "page 2.html" or "notes 3"
SYNC_COPY = re.compile(r" \d+(\.[^./]+)?$")

# Hosts of secondary copies that are commentary or press rather than official publications.
THIRD_PARTY_HOSTS = {
    "www.transparencycoalition.ai", "www.chinalawtranslate.com", "cset.georgetown.edu", "asociace.ai",
    "basham.com.mx", "naswnv.socialworkers.org", "www.skadden.com", "www.tilleke.com", "www.morogluarseven.com",
    "www.nixonpeabody.com", "www.vietnamplus.vn", "www.ultimahora.com", "www.bta.bg", "gna.org.gh", "qanoon.om",
}


def host_of(f):
    return (urllib.parse.urlsplit(f.get("final_url") or f.get("url") or "").hostname or "").lower()


def is_third_party(f):
    return host_of(f) in THIRD_PARTY_HOSTS


JWT_RE = re.compile(rb"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
PLACEHOLDER = b"REDACTED-ACCESS-TOKEN"
TEXT_SUFFIXES = {".html", ".htm", ".txt", ".json", ".xml", ".js"}


def live_tokens(data, now=None):
    """JWTs in a file that are still valid: unexpired, or without an expiry. Expired tokens are left alone."""
    now = now or dt.datetime.now(dt.timezone.utc).timestamp()
    found = {}
    for m in JWT_RE.finditer(data):
        tok = m.group(0)
        try:
            part = tok.split(b".")[1]
            payload = json.loads(base64.urlsafe_b64decode(part + b"=" * (-len(part) % 4)))
        except Exception:
            continue  # looks like a JWT but is not one
        exp = payload.get("exp") if isinstance(payload, dict) else None
        if isinstance(exp, (int, float)) and exp < now:
            continue
        found[tok] = payload if isinstance(payload, dict) else {}
    return found


def redaction_plan(files):
    """path -> (published bytes, note) for stored text files that carry live tokens."""
    plan = {}
    for f in files:
        if not f["in_archive_dataset"] or Path(f["path"]).suffix.lower() not in TEXT_SUFFIXES:
            continue
        data = (ROOT / f["path"]).read_bytes()
        toks = live_tokens(data)
        if not toks:
            continue
        new = data
        for tok in toks:
            new = new.replace(tok, PLACEHOLDER)
        issuers = sorted({str(p.get("iss") or "unknown issuer") for p in toks.values()})
        note = ("%d access token(s) embedded by the source page (issued by %s) replaced with %s; "
                "the rest of the file is unchanged" % (len(toks), ", ".join(issuers), PLACEHOLDER.decode()))
        plan[f["path"]] = (new, note)
    return plan


# ----------------------------------------------------------------------------- tables

def quoted_files(db):
    """path -> record IDs, for every stored file quoted as evidence in data/history.jsonl or data/definitions.json."""
    out = defaultdict(set)
    for e in history.load():
        for it in e.get("evidence") or []:
            if isinstance(it, dict) and it.get("file"):
                out[it["file"]].add(e.get("record_id"))
    defs = ROOT / "data" / "definitions.json"
    for d in (json.load(open(defs, encoding="utf-8")) if defs.is_file() else {}).get("definitions") or []:
        if d.get("file"):
            out[d["file"]].add(d.get("record_id"))
    return out


def known_urls(db):
    """path -> (url, final_url) of the files the pipeline runs stored (runs/*/sources.json)."""
    urls = {}
    for s in sorted((ROOT / "runs").glob("*/sources.json")):
        try:
            entries = json.load(open(s, encoding="utf-8"))
        except ValueError:
            continue
        for ent in entries.values():
            for blk in [ent.get("main") or {}] + list((ent.get("extras") or {}).values()):
                for f in (blk or {}).get("files") or []:
                    if f.get("path"):
                        urls[f["path"]] = (f.get("url"), f.get("final_url"))
    return urls


STORED_ROLE = re.compile(r"^(official-print|official-rendered|official|secondary|provided|document-\d+)(?:-(\d+))?$")
STATUSES = ("current", "earlier version", "no longer used", "run copy", "register file")
OFFICIAL_ROLES = ("official", "official-rendered", "official-print", "provided")


def role_of(name):
    """The archiver's role of a stored file and its copy number, from the file name: official.pdf -> (official, 1),
    official-2.html (a second copy stored the same day) -> (official, 2), document-3.pdf -> (document-3, 1)."""
    m = STORED_ROLE.match(name.split(".", 1)[0])
    return (m.group(1), int(m.group(2) or 1)) if m else (name.split(".", 1)[0], 1)


def past_urls(db):
    """(record ID, field) -> every value official_url or secondary_url had, from the record and its history."""
    past = defaultdict(set)
    for r in db["records"]:
        for k in ("official_url", "secondary_url"):
            if r.get(k):
                past[(r["id"], k)].add(r[k])
    for e in history.load():
        if e.get("field") in ("official_url", "secondary_url"):
            for v in (e.get("old"), e.get("new")):
                if isinstance(v, str) and v:
                    past[(e.get("record_id"), e["field"])].add(v)
    return past


def other_row(rid, path, archive_repo_url, status, role, url=None, final=None, third=False, retrieved=None,
              replaced_by=None):
    """A source_files row for a stored file that is not one of a record's current copies."""
    p = ROOT / path
    present = p.is_file()
    published = present and not third
    digest = hashlib.sha256(p.read_bytes()).hexdigest() if present else None
    return {
        "record_id": rid, "role": role, "path": path, "url": url, "final_url": final,
        "host": host_of({"url": url, "final_url": final}), "http_status": None, "content_type": None,
        "bytes": p.stat().st_size if present else None, "sha256": digest, "retrieved_at": retrieved, "last_checked": None,
        "method": None, "stale": False, "integrity": "ok" if present else None, "in_archive_dataset": published,
        "archive_url": "%s/blob/main/%s" % (archive_repo_url, path) if published else None,
        "redacted": False, "published_sha256": digest if published else None, "redaction_note": None,
        "status": status, "replaced_by": replaced_by, "replaced_on": replaced_by.split("/")[2] if replaced_by else None,
        "quoted": False, "_missing": not present,
    }


def earlier_rows(db, current, archive_repo_url, past):
    """Every other copy the archiver stored under archive/<ID>/<date>/ (its SHA256SUMS lists them): earlier versions
    that a newer copy replaced, or copies of a source the record no longer has. Each earlier version names the file
    that replaced it: the current copy whose previous_path it is, else the next newer copy of the same role, else (for
    an official copy stored another way before) the record's current official copy. A second identical copy stored on
    the same day is left out. A copy counts as third-party when any URL its record's field ever had is."""
    by = {r["id"]: r for r in db["records"]}
    after = {}  # earlier path -> the current copy that replaced it (the archiver's previous_path link)
    official_now = {}  # record -> its current official copy, for official copies stored another way before
    for r in db["records"]:
        files = [f for f in (r.get("local_copy") or {}).get("files") or [] if f.get("path")]
        for f in files:
            if f.get("previous_path"):
                after[f["previous_path"]] = f["path"]
        for role in OFFICIAL_ROLES:
            hit = next((f["path"] for f in files if role_of(Path(f["path"]).name)[0] == role and not f.get("stale")), None)
            if hit:
                official_now[r["id"]] = hit
                break
    copies = defaultdict(list)  # (record, role) -> [(date, copy number, path, sha256)]
    for sums in sorted((ROOT / "archive").glob("*/*/SHA256SUMS")):
        rid, date = sums.parent.parent.name, sums.parent.name
        if rid not in by:
            continue  # archive/_runs, archive/_provided and folders of no record
        for line in sums.read_text(encoding="utf-8").splitlines():
            if "  " in line:
                digest, name = line.split("  ", 1)
                role, n = role_of(name)
                copies[(rid, role)].append((date, n, "archive/%s/%s/%s" % (rid, date, name), digest))
    rows = []
    for (rid, role), items in sorted(copies.items()):
        items.sort()
        sha_of = {path: digest for _, _, path, digest in items}
        for i, (date, n, path, digest) in enumerate(items):
            if path in current or not (ROOT / path).is_file():
                continue
            nxt = after.get(path) or next((x[2] for x in items[i + 1:]), None)
            if not nxt and role in OFFICIAL_ROLES:
                nxt = official_now.get(rid)  # the official source is stored another way now (e.g. no longer rendered)
            if nxt and sha_of.get(nxt) == digest and nxt.split("/")[2] == date:
                continue  # the same bytes stored twice on one day; an identical copy from an earlier day stays, since a
                # citation of an earlier version names its path
            field = "secondary_url" if role == "secondary" else "official_url"
            cands = past.get((rid, field), set())
            url = next(iter(cands)) if len(cands) == 1 and not role.startswith("document") else None
            rows.append(other_row(rid, path, archive_repo_url, "earlier version" if nxt else "no longer used",
                                  ROLE_LABELS.get(role, role), url=url,
                                  third=any(is_third_party({"url": u}) for u in cands), retrieved=date,
                                  replaced_by=nxt))
    return rows


def first_copies():
    """path -> record ID, for the copies a discover run stored that were a new record's first local copy (pass.json);
    the archiver stores the record's later copies under archive/<ID>/, so these became earlier versions."""
    out = {}
    for p in sorted((ROOT / "runs").glob("*/pass.json")):
        try:
            records = json.load(open(p, encoding="utf-8")).get("records") or []
        except ValueError:
            continue
        for rec in records:
            for f in (rec.get("local_copy") or {}).get("files") or []:
                if f.get("path") and rec.get("id"):
                    out[f["path"]] = rec["id"]
    return out


def first_copy_rows(db, listed, archive_repo_url):
    """Earlier versions among the first copies of records made by discover runs (see first_copies)."""
    now = {}  # (record, role) -> current path
    for r in db["records"]:
        for f in (r.get("local_copy") or {}).get("files") or []:
            if f.get("path") and not f.get("stale"):
                now.setdefault((r["id"], role_of(Path(f["path"]).name)[0]), f["path"])
    rows = []
    for path, rid in sorted(first_copies().items()):
        if path in listed or not (ROOT / path).is_file():
            continue
        role = role_of(Path(path).name)[0]
        nxt = now.get((rid, role)) or (next((now[(rid, x)] for x in OFFICIAL_ROLES if (rid, x) in now), None)
                                       if role in OFFICIAL_ROLES else None)
        rows.append(other_row(rid, path, archive_repo_url, "earlier version" if nxt else "no longer used",
                              ROLE_LABELS.get(role, role), replaced_by=nxt))
    return rows


def run_rows(db, listed, archive_repo_url, past):
    """The quoted files that are neither a record's copy nor an earlier version: copies a pipeline run stored
    (archive/_runs/...), and register files such as a quality check's findings. They are published so that every
    quote in the history and the definitions can be checked against the file it names."""
    urls = known_urls(db)
    rows = []
    for path, rids in sorted(quoted_files(db).items()):
        if path in listed:
            continue
        rid = sorted(x for x in rids if x)[0] if any(rids) else None
        url, final = urls.get(path, (None, None))
        if url:
            third = is_third_party({"url": url, "final_url": final})
        else:
            field = "secondary_url" if Path(path).name.startswith("secondary") else "official_url"
            cands = set().union(*(past.get((x, field), set()) for x in rids)) if rids else set()
            url = next(iter(cands)) if len(cands) == 1 else None
            third = any(is_third_party({"url": u}) for u in cands)
        run = path.startswith("archive/_runs/")
        status = "run copy" if run else ("no longer used" if path.startswith("archive/") else "register file")
        rows.append(other_row(rid, path, archive_repo_url, status,
                              "copy stored by run %s" % path.split("/")[2] if run else status,
                              url=url, final=final, third=third))
    return rows


def tables(db, archive_repo_url):
    R = db["records"]
    records, topics, related, files = [], [], [], []
    for r in R:
        flat = build.flat(r)
        flat["safety_topics"] = list(r.get("safety_topics") or [])
        flat["related_ids"] = [x["id"] for x in (r.get("related") or []) if x.get("id")]
        flat.pop("local_files", None)
        flat.pop("local_sha256", None)
        records.append(flat)
        topics += [{"record_id": r["id"], "topic": t} for t in r.get("safety_topics") or []]
        related += [{"record_id": r["id"], "related_id": x["id"]} for x in r.get("related") or [] if x.get("id")]
        for f in (r.get("local_copy") or {}).get("files") or []:
            present = bool(f.get("path")) and (ROOT / f["path"]).is_file()
            published = present and not is_third_party(f)
            files.append({
                "record_id": r["id"], "role": f.get("label") or f.get("role"), "path": f.get("path"),
                "url": f.get("url"), "final_url": f.get("final_url"), "host": host_of(f),
                "http_status": f.get("http_status"), "content_type": f.get("content_type"), "bytes": f.get("bytes"),
                "sha256": f.get("sha256"), "retrieved_at": f.get("retrieved_at"), "last_checked": f.get("last_checked"),
                "method": f.get("method"), "stale": bool(f.get("stale")), "integrity": f.get("integrity"),
                "in_archive_dataset": published,
                "archive_url": "%s/blob/main/%s" % (archive_repo_url, f["path"]) if published else None,
                "redacted": False, "published_sha256": f.get("sha256") if published else None, "redaction_note": None,
                "status": "current", "replaced_by": None, "replaced_on": None, "quoted": False, "_missing": not present,
            })
    past = past_urls(db)
    files += earlier_rows(db, {f["path"] for f in files if f.get("path")}, archive_repo_url, past)
    files += first_copy_rows(db, {f["path"] for f in files if f.get("path")}, archive_repo_url)
    files += run_rows(db, {f["path"] for f in files if f.get("path")}, archive_repo_url, past)
    quoted = quoted_files(db)
    for row in files:
        row["quoted"] = row.get("path") in quoted
    plan = redaction_plan(files)
    for row in files:
        if row["path"] in plan:
            data, note = plan[row["path"]]
            row.update({"redacted": True, "published_sha256": hashlib.sha256(data).hexdigest(), "redaction_note": note})
    return records, topics, related, files, plan


def write_parquet(rows, path, schema):
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path, compression="zstd")


def schemas():
    import pyarrow as pa
    s, i, b = pa.string(), pa.int64(), pa.bool_()
    rec_fields = []
    for c in build.CSV_COLS:
        if c in ("local_files", "local_sha256"):
            continue
        rec_fields.append(pa.field(c, pa.list_(s) if c in ("safety_topics", "related_ids") else s))
    return {
        "records": pa.schema(rec_fields),
        "topics": pa.schema([("record_id", s), ("topic", s)]),
        "related": pa.schema([("record_id", s), ("related_id", s)]),
        "definitions": pa.schema([("id", s), ("record_id", s), ("term", s), ("term_group", s), ("definition", s),
                                  ("english", s), ("english_by", s), ("language", s), ("locator", s), ("text_layer", s),
                                  ("source_changed", pa.bool_()), ("file", s), ("sha256", s), ("run_id", s)]),
        "history": pa.schema([("date", s), ("run_id", s), ("record_id", s), ("event", s), ("field", s), ("old", s),
                              ("new", s), ("reason", s), ("evidence", s), ("tool", s), ("model", s)]),
        "source_files": pa.schema([("record_id", s), ("role", s), ("path", s), ("url", s), ("final_url", s), ("host", s),
                                   ("http_status", i), ("content_type", s), ("bytes", i), ("sha256", s),
                                   ("retrieved_at", s), ("last_checked", s), ("method", s), ("stale", b),
                                   ("integrity", s), ("in_archive_dataset", b), ("archive_url", s),
                                   ("redacted", b), ("published_sha256", s), ("redaction_note", s), ("status", s),
                                   ("replaced_by", s), ("replaced_on", s), ("quoted", b)]),
    }


# ----------------------------------------------------------------------------- cards

def stats(db, files):
    R = db["records"]
    lv = Counter(r["verification"]["level"] for r in R)
    force = Counter(r["legal_force"] for r in R)
    countries = {r["country"] for r in R if r["jurisdiction_level"] in ("National", "Sub-national")}
    states = {r["jurisdiction"] for r in R if r["jurisdiction_level"] == "Sub-national" and r["country"] == "United States"}
    intl = sum(1 for r in R if r["jurisdiction_level"] in ("International", "Supranational"))
    pub = [f for f in files if f["in_archive_dataset"]]
    return {
        "n": len(R), "A": lv["A"], "B": lv["B"], "C": lv["C"], "binding": force["Binding"],
        "nonbinding": force["Non-binding"], "proposed": force["Proposed"], "countries": len(countries),
        "states": len(states), "intl": intl, "files": len(files), "pub_files": len(pub),
        "pub_mb": sum(f["bytes"] or 0 for f in pub) / 1e6,
        "missing": sum(1 for f in files if f.get("_missing")),
        "n_current": sum(1 for f in files if f.get("status") == "current" and f["in_archive_dataset"]),
        "n_earlier": sum(1 for f in files if f.get("status") == "earlier version" and f["in_archive_dataset"]),
        "n_unused": sum(1 for f in files if f.get("status") == "no longer used" and f["in_archive_dataset"]),
        "n_run": sum(1 for f in files if f.get("status") == "run copy" and f["in_archive_dataset"]),
        "n_register": sum(1 for f in files if f.get("status") == "register file" and f["in_archive_dataset"]),
        "excluded": sum(1 for f in files if not f["in_archive_dataset"] and not f.get("_missing")),
        "redacted": sum(1 for f in files if f.get("redacted")),
        "with_copy": sum(1 for r in R if (r.get("local_copy") or {}).get("status") == "archived"),
        "years": "%s to %s" % (min(r["date_published"][:4] for r in R if r.get("date_published")),
                               max(r["date_published"][:4] for r in R if r.get("date_published"))),
        "from_2023": build.numbers(db)["from_2023"], "before_2023": build.numbers(db)["before_2023"],
    }


def bibtex(meta, repo_url):
    return build.bibtex(meta, repo_url)


def dataset_card(db, st, ns, name, github_url):
    meta = db["meta"]
    repo_url = "https://huggingface.co/datasets/%s/%s" % (ns, name)
    archive_url = repo_url + "-archive"
    space_url = "https://huggingface.co/spaces/%s/%s" % (ns, name)
    authors = ", ".join("%s %s" % (f, l) for l, f in AUTHORS)
    yaml = """---
license: cc-by-4.0
language:
- en
pretty_name: %s
size_categories:
- n<1K
annotations_creators:
- machine-generated
source_datasets:
- original
tags:
- ai-policy
- ai-safety
- ai-regulation
- ai-governance
- law
- legislation
- government
configs:
- config_name: records
  data_files: data/records.parquet
  default: true
- config_name: topics
  data_files: data/topics.parquet
- config_name: related
  data_files: data/related.parquet
- config_name: source_files
  data_files: data/source_files.parquet
%s%s---
""" % (PRETTY_NAME, "- config_name: history\n  data_files: data/history.parquet\n" if st.get("n_history") else "",
       "- config_name: definitions\n  data_files: data/definitions.parquet\n" if st.get("n_definitions") else "")
    body = """
# {pretty}

**A pipeline of AI agents that anyone can rerun, and the register it maintains.** The pipeline, in the [GitHub repository]({github}), searches official sites, writes each record from a stored copy of its source with quoted evidence, has a second model check every field, and records every change. You can rerun it with your own Claude Code or Codex subscription, or with another model, and compare your records with this dataset field by field. The maintainers rerun it over the full register at least once a month.

The register holds {n} official instruments on AI safety and AI regulation, from {countries} countries, including sub-national records for {states} US states, and from intergovernmental bodies such as the UN, the OECD, the G7, the G20 and the Council of Europe. It covers laws, implementing regulations, executive orders, government frameworks and guidelines, AI safety institute mandates, national strategies with safety content, treaties, declarations and pending bills, from {years}. Each record links to its official source and says how it was verified.

Despite the name, it is not every AI policy: scope is limited to official instruments on AI safety and regulation, coverage is densest from 2023 on, and the coverage section below lists what is still missing. Guidance from supervisory authorities (financial, insurance and health supervisors, data protection authorities, equality bodies) and standards bodies (CEN-CENELEC, ETSI, ISO/IEC) was added to the scope in October 2026 and has not been searched systematically yet.

- **Browse it:** [{pretty} on Spaces]({space}), with search, filters, a chart, record pages and citations.
- **Source documents:** [{ns}/{name}-archive]({archive}), the stored copies of the official sources with SHA-256 hashes. Open to anyone with a free Hugging Face account.
- **Snapshot:** {snapshot}, data version {version}. Statuses are as of the snapshot.
- **Open questions:** {n_open_questions} records have a question only a maintainer can settle; each is an [issue on GitHub]({github}/issues?q=is%3Aissue+is%3Aopen+label%3Aquestion), and the `open_questions` column links it. Until it is decided, the record keeps its last checked values.
{changes_md}
## How it was made

The records are an **AI-based extraction**. AI agents researched each instrument, fetched its official page or document, confirmed the title, date and status there, and wrote the summary, the status notes, the topic tags and a verification level.

| | |
|---|---|
| Agent | Claude Code, Anthropic's agentic coding tool, with its web search and web fetch tools; research passes and quality checks ran as agents following `AGENTS.md` |
| Model | Claude Fable 5.1 (`claude-fable-5-1`), for the research passes and the two quality checks of version 1. Later pipeline runs and checks name their models in `meta.provenance` and in each run's report; the first refresh run extracted with Claude Opus 5.5 and checked with Claude Sonnet 5.5, and the translation check used Claude Opus 5.5 |
| Other tools | a Python archiver that stores each source with its SHA-256 hash, headless Chromium for pages that need JavaScript, pypdf and Tesseract OCR for PDF text |
| Research dates | 11 and 12 October 2026, in twelve research passes and two quality checks; `meta.provenance` in `raw/records.json` logs them |
| Human review | Michael Riegler checked 50 randomly chosen records by hand and found no problems |
| Updates | The maintainers rerun the pipeline over the full register at least once a month; each run is recorded in the history |

Agents are what made this register possible: {n} instruments from {countries} countries, each checked against its official source and stored with a hash, in two days. They also make it repeatable. The method is written down in `AGENTS.md`, complete enough for another agent to follow, so anyone can extend the register, re-verify it after laws change, or rerun the method with a different model and compare the results. Every record carries its evidence, so checking a record does not depend on trusting whoever wrote it. A rerun gives comparable records, not identical ones, because language models are not deterministic.

No human has reviewed every record. The hand check of 50 records rules out frequent errors, not occasional ones: with no problems in 50, the error rate is probably below about 6 percent. Two content quality checks, in which a second agent compared the records with their stored sources, are in `docs/`, with what was fixed and what is still open.

| Verification level | Meaning | Records |
|---|---|---:|
| A | The instrument's own official text, or an official register (gazette, law database, legislative record), was stored and confirmed the title, date and status | {A} |
| B | Another official source confirmed them (an announcement by the issuer, a page of another official body, an official translation, the OECD.AI entry) | {B} |
| C | No official page could be fetched; the record rests on at least two independent secondary sources and says CAUTION | {C} |

Check the level before citing a record, and re-check level C records against the original.

How the level was set depends on when a record was made. For the records of version 1, made before the pipeline, the agent that wrote each record also assigned its level; the two quality checks and the hand check of 50 records reviewed them. Records the pipeline adds or re-verifies get their level from a script that checks each quoted piece of evidence against the stored copy and the host it came from, and their History section names the run.

## Languages and translation

The register does not translate the instruments it lists. About a third of the records rest on a text that is not in English. For those, the summary was written in English by an AI agent that read the original as machine-extracted text, and the English title is the agent's rendering unless `english_version` names an English text of the issuer or a government translation (usually provisional, without legal force). For point-by-point work, quote and cite the original or that translation, not the summary.

A translation check on 14 October 2026, by a second model (Claude Opus 5.5), compared 58 such records with their stored originals: every Chinese, Japanese, Korean and Vietnamese record and a random sample of 20 others. The English titles were accurate. Of 175 specific summary claims, 73 percent rendered the original accurately and 10 percent overstated, understated or mistranslated it; about one defined legal term in five was a near-synonym of the original's term. Six records had an error that changes the legal meaning, and 13 could not be checked because the stored copy lacks the instrument's own text. The report is `docs/translation-check-2026-10-14.md` in the [GitHub repository]({github}).

## Quick start

```python
from datasets import load_dataset

records = load_dataset("{ns}/{name}", "records", split="train")
binding = records.filter(lambda r: r["legal_force"] == "Binding")
```

```python
import pandas as pd

df = pd.read_parquet("hf://datasets/{ns}/{name}/data/records.parquet")
df.groupby(["region", "legal_force"]).size().unstack(fill_value=0)
```

## Contents

| Config | Rows | One row per |
|---|---:|---|
| `records` (default) | {n} | instrument |
| `topics` | {n_topics} | instrument and safety topic |
| `related` | {n_related} | link between two records |
| `source_files` | {files} | stored copy of a source, with URL, hash, retrieval time and a link into the archive dataset; `status` says whether it is a record's `current` copy, an `earlier version` (with `replaced_by` and `replaced_on`), `no longer used`, a `run copy` or a `register file`, and `quoted` whether the history or the definitions quote it; `redacted` marks the few published copies in which a live access token embedded by the source site was replaced |
{history_row}{definitions_row}
`raw/records.json` is the full nested source of truth, with the complete verification and local-copy history of each record. `raw/records.csv` and `raw/register.xlsx` hold the same records for spreadsheets.

### Fields of `records`

| Field | Meaning |
|---|---|
| `id` | Register ID: jurisdiction code plus sequence, e.g. `EU-03`, `US-CA-05` |
| `title`, `short_title`, `original_title` | Official title (official English title where one exists), common short name, title in the original language |
| `jurisdiction`, `country`, `jurisdiction_level`, `region` | Issuing country, bloc or body; International, Supranational, National or Sub-national; world region |
| `issuing_body` | The institution that adopted or issued the instrument |
| `instrument_type` | Law, regulation or implementing rule, executive order or decree, guidelines or framework, voluntary code, technical standard, institutional mandate, declaration, treaty, resolution, bill, strategy or action plan, report |
| `legal_force` | Binding, Non-binding or Proposed |
| `status` | In force, partially in force, adopted but not yet in force, published (non-binding), draft, superseded, revoked or lapsed |
| `date_published`, `date_in_force`, `date_last_updated` | ISO dates; `YYYY-MM` or `YYYY` when the source gives no exact day. `date_published` is the date of the act itself (adoption, signature or issue) |
| `official_identifier` | The citable number: law or decree number, gazette reference, bill number, UN symbol, CELEX |
| `official_url`, `secondary_url` | The official source and, where useful, a second authoritative source |
| `language` | Language(s) of the official text |
| `english_version`, `english_version_url`, `english_version_by` | Whether an English text exists: `authentic` (English is one of the official texts), `government translation` (by the issuer or another public body; usually provisional, without legal force), `third-party translation` (by anyone else) or `none found`, with the link and who translated it. Empty: not checked yet. See "Languages and translation" |
| `summary`, `notes` | What the instrument does, with its safety content; status details, phased dates and discrepancies between sources |
| `scope_note` | Empty for an instrument clearly in scope; for a borderline one, why it is included. The register is inclusive and flags such cases instead of leaving them out |
| `safety_topics` | List of topics from a fixed vocabulary of 17, e.g. `general-purpose / frontier AI`, `incident reporting`, `child safety` |
| `related_ids` | IDs of related records |
| `verification_level`, `verified_on`, `verification_method`, `verification_note`, `second_check` | How and when the record was checked, and what rests on secondary sources |
| `local_status`, `local_flag`, `local_last_attempt` | Whether the official source is stored in the archive dataset, and why not if it is not |

## Coverage

**Time coverage.** The register aims to hold every instrument within its scope, but so far it is densest from 2023 on: {from_2023} records date from 2023 or later and {before_2023} from earlier years. Older instruments are being added run by run; the absence of one from before 2023 says nothing about whether it exists.

{binding} binding, {nonbinding} non-binding and {proposed} proposed instruments; {intl} records are international or EU instruments. Every G20 member and 25 of the 27 EU member states have at least one record. Belgium and Estonia had adopted no national AI Act implementing measure at the snapshot.

The "Method & coverage" page of the Space lists what is known to be missing: instruments not adopted yet, instruments reported by secondary sources but not confirmed on an official page, and the records with weaker evidence. A country's absence from the register does not mean it has no AI instruments.

## Limitations

- Extraction errors are possible. Dates can be misread, a status can lag behind an amendment, and a summary can over- or under-state an instrument. Non-English documents were read as machine-extracted text and summarised in English.
- Statuses change. The register is a snapshot; it does not follow amendments after {snapshot}.
- For {nocopy} records the official source is either not stored or stored in a form that needs review, such as a bot-check page, mostly because the official site blocks automated downloads. Their `local_flag` says why.
- Nothing here is legal advice.

## License

The records, summaries and notes are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Titles, dates and identifiers of official instruments are facts. The stored source documents in the archive dataset remain under their publishers' terms.

## Citation

```bibtex
{bibtex}
```

Authors: {authors} ({affiliation}). Please say in your own text that the register is an AI-assisted extraction, and name the verification level of the records you rely on.

## Corrections and updates

Everything a person adds goes through an issue on [GitHub]({github}): *Suggest an instrument* for a missing instrument or news about a record, *Provide a document* for a source the archiver cannot download, and a comment on an issue labelled `question` to help settle an open question. A maintainer decides with one line, the next pipeline run applies it, and the change is recorded in the history with the issue link. The README's "How to contribute" section explains the mechanism.

## Contact

For anything the issue forms do not cover, or that should not be public, write to the maintainers: {contact}.
""".format(pretty=PRETTY_NAME, space=space_url, contact=CONTACT, archive=archive_url, ns=ns, name=name,
           snapshot=meta.get("snapshot_date"), version=meta.get("version"), github=github_url,
           bibtex=bibtex(meta, repo_url), authors=authors, affiliation=AFFILIATION,
           nocopy=st["n"] - st["with_copy"],
           history_row=("| `history` | %d | event in a record's history: added, a field changed, re-verified without change, "
                        "checked by a human, a scope decision; `old`, `new` and `evidence` are JSON text. `HISTORY.md` is the "
                        "readable version |\n" % st["n_history"]) if st.get("n_history") else "",
           definitions_row=("| `definitions` | %d | defined term of an instrument (\"AI system\", \"model\" and others), quoted "
                            "verbatim from its stored source with the article or section; a pilot of the crosswalk "
                            "between instruments. Similar definitions are not legally equivalent |\n" % st["n_definitions"])
           if st.get("n_definitions") else "", **st)
    return yaml + body


def archive_card(st, ns, name):
    main = "https://huggingface.co/datasets/%s/%s" % (ns, name)
    yaml = """---
license: other
license_name: publishers-terms
license_link: LICENSE.md
pretty_name: %s (source documents)
tags:
- ai-policy
- legislation
- government
extra_gated_heading: Access the stored source documents
extra_gated_prompt: >-
  These files are copies of official publications by governments, legislatures and intergovernmental bodies,
  stored so that each record of the register can be traced to the exact document it was based on. Each file
  remains subject to its publisher's terms. Access needs a Hugging Face account so that automated crawlers do
  not harvest the files; requests are approved automatically.
extra_gated_fields:
  Affiliation: text
  Intended use: text
  I will use the documents for research or verification and respect each publisher's terms: checkbox
extra_gated_button_content: Access the documents
---
""" % PRETTY_NAME
    body = """
# {pretty}: source documents

Stored copies of the official sources behind the records of [{ns}/{name}]({main}): {pub_files} files, about {pub_mb:.0f} MB, mostly PDFs and HTML pages of laws, decrees, gazette entries, guidelines and declarations.

Each file sits at `archive/<record ID>/<retrieval date>/`, next to a `SHA256SUMS` file:

```bash
cd archive/EU-03/2026-10-11 && sha256sum -c SHA256SUMS
```

## Which copy is which

A record can have several copies of the same source: the archiver stores a new copy whenever the visible text of a source changes, and keeps the earlier ones. The folder date is the day a copy was stored, so the newest folder is not always the current copy (a record's official text can date from one day and its secondary source from another). `FILES.csv`, next to this card, lists every published file with its record, its role and its status:

| Status | Files | What it is |
|---|---:|---|
| `current` | {n_current} | a copy the record uses now; the app and the record's `local_copy` point to it |
| `earlier version` | {n_earlier} | a copy that a newer one replaced; `replaced_by` names the newer file and `replaced_on` the day the newer file was stored |
| `no longer used` | {n_unused} | a copy of a source the record no longer has, such as a linked document its official page no longer links |
| `run copy` | {n_run} | a source a pipeline run stored under `archive/_runs/<run ID>/<candidate>/` and quoted as evidence |
| `register file` | {n_register} | a file of the register itself that its history quotes, such as a quality check's findings |

The column `quoted` says whether the register's history or definitions quote the file as evidence. The main dataset's `source_files` table has the same columns for these files and for the third-party copies that are not published here.

A release adds files and never deletes them, so every earlier version stays here and every quote can be checked against the file it names. Version 1.17 was the exception: it removed 189 files from this branch, mostly earlier versions (they remain in the revision tagged `v1.16`); version 1.18 restored them and stopped releases from deleting files.

## What is not included

{excluded} copies of third-party pages that served as secondary sources (law-firm alerts, newspaper articles, NGO and think-tank pages) are not published here, because they are not official publications. Their URLs and hashes are in `source_files`, marked `in_archive_dataset = false`.

Some stored files are bot-check pages or empty JavaScript shells that an official site returned instead of the document; the record's `local_flag` in the main dataset says so.

## Redacted access tokens

{redacted} stored page(s) carried live access tokens that the source site embeds in its own scripts, such as a commenting service's login token. In the published copy each such token is replaced with `REDACTED-ACCESS-TOKEN`; nothing else in the file changed. `REDACTIONS.md` lists the files with their original and published hashes, and `SHA256SUMS` lists the published files. Expired tokens are left as they were.

## Terms

The documents remain under their publishers' terms (see `LICENSE.md`). If you hold rights in a file and want it removed, open a discussion on this dataset naming the path, or write to the maintainers: {contact}.
""".format(pretty=PRETTY_NAME, ns=ns, name=name, main=main, contact=CONTACT, **st)
    lic = """# Terms for the stored source documents

The files in `archive/` are copies of documents published by governments, legislatures, courts, regulators and intergovernmental organisations. They are stored for research and to verify the records of the register. Copyright and reuse terms are those of each publisher; many official texts are in the public domain or under open government licences, and some are not. The register's authors claim no rights in them.

The register's own records, summaries and notes are licensed separately under CC BY 4.0 in the main dataset.
"""
    return yaml + body, lic


def space_card(ns, name, github_url):
    return """---
title: Every AI Policy Ever
emoji: 📜
colorFrom: blue
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: cc-by-4.0
short_description: Searchable register of official AI safety rules
datasets:
- {ns}/{name}
- {ns}/{name}-archive
---

# Every AI Policy Ever

A pipeline of AI agents that anyone can rerun, and the searchable register of official AI safety and AI regulation instruments it maintains: laws, executive orders, frameworks, AI safety institute mandates, declarations and bills from governments and intergovernmental bodies. Each record links to its official source, says how it was verified, and has a ready-made citation. The pipeline is on [GitHub]({github}): rerun it and compare your records with these.

The records are an AI-based extraction, made by AI agents in Claude Code with the model Claude Fable 5.1 and spot-checked by hand; the [dataset card](https://huggingface.co/datasets/{ns}/{name}) explains the method, why it is repeatable, and its limits. The data can be downloaded from the [dataset](https://huggingface.co/datasets/{ns}/{name}), and the stored source documents from the [archive dataset](https://huggingface.co/datasets/{ns}/{name}-archive).

Suggestions, corrections and documents a site blocks go through the issue forms on [GitHub]({github}); the app's Contribute tab explains how. For anything else, write to the maintainers: {contact}.
""".format(ns=ns, name=name, github=github_url, contact=CONTACT)


# ----------------------------------------------------------------------------- build

def build_all(out, ns, name, github_url, changes_md=""):
    db = build.normalise(build.load())
    errors, _ = validate.run(db, quiet=True)
    if errors:
        raise SystemExit("records.json has %d validation error(s); run tools/validate.py" % len(errors))
    repo_url = "https://huggingface.co/datasets/%s/%s" % (ns, name)
    records, topics, related, files, plan = tables(db, repo_url + "-archive")
    st = stats(db, files)
    st["n_topics"], st["n_related"] = len(topics), len(related)
    st["changes_md"] = changes_md
    st["n_history"] = len(history.load())
    defs = build.definitions_table(db)
    st["n_definitions"] = len(defs)
    st["n_open_questions"] = len(build.open_questions())
    # register.sqlite and register.xlsx are generated but not in git, so a pull leaves them as they were: write them
    # from the data now, so that the raw files of the dataset are never older than records.json
    build.write_sqlite(db, ROOT)
    try:
        import export_xlsx
        export_xlsx.write_xlsx(db, ROOT)
        fresh_xlsx = True
    except ImportError:  # openpyxl is optional; without it the dataset gets no register.xlsx rather than an old one
        fresh_xlsx = False
    if out.exists():
        shutil.rmtree(out)
    ds, ar, sp = out / "dataset", out / "archive", out / "space"

    # dataset
    (ds / "data").mkdir(parents=True)
    sch = schemas()
    write_parquet(records, ds / "data" / "records.parquet", sch["records"])
    write_parquet(topics, ds / "data" / "topics.parquet", sch["topics"])
    write_parquet(related, ds / "data" / "related.parquet", sch["related"])
    if defs:  # the definitions layer of the crosswalk (issue #70)
        write_parquet([{k: d.get(k) for k in sch["definitions"].names} for d in defs], ds / "data" / "definitions.parquet",
                      sch["definitions"])
    write_parquet([{k: v for k, v in f.items() if not k.startswith("_")} for f in files], ds / "data" / "source_files.parquet",
                  sch["source_files"])
    hist = []
    for e in history.load():
        row = {k: e.get(k) for k in history.KEYS}
        for k in ("old", "new", "evidence"):
            row[k] = None if row[k] is None else (row[k] if isinstance(row[k], str) else json.dumps(row[k], ensure_ascii=False))
        hist.append(row)
    if hist:  # no history table until the first pipeline run has written events
        write_parquet(hist, ds / "data" / "history.parquet", sch["history"])
    (ds / "raw").mkdir()
    for f in ("records.json", "records.csv", "register.xlsx", "history.jsonl", "definitions.json", "definitions.csv"):
        if (ROOT / "data" / f).is_file() and (f != "register.xlsx" or fresh_xlsx):
            shutil.copy2(ROOT / "data" / f, ds / "raw" / f)
    if (ROOT / "HISTORY.md").is_file():
        shutil.copy2(ROOT / "HISTORY.md", ds / "HISTORY.md")
    shutil.copy2(ROOT / "AGENTS.md", ds / "AGENTS.md")
    if (ROOT / "docs").is_dir():
        shutil.copytree(ROOT / "docs", ds / "docs", ignore=lambda d, names: [n for n in names if SYNC_COPY.search(n)])
    (ds / "README.md").write_text(dataset_card(db, st, ns, name, github_url), encoding="utf-8")

    # archive: official copies only, with SHA256SUMS rewritten to list what is published
    by_dir = defaultdict(list)
    for f in files:
        if f["in_archive_dataset"]:
            src = ROOT / f["path"]
            dst = ar / f["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if f["path"] in plan:
                dst.write_bytes(plan[f["path"]][0])  # a new file, so the local exact copy is never touched
            else:
                try:
                    dst.hardlink_to(src)
                except (OSError, AttributeError):
                    shutil.copy2(src, dst)
            by_dir[dst.parent].append((f["published_sha256"], dst.name))
    for folder, entries in by_dir.items():
        lines = sorted(set("%s  %s" % e for e in entries), key=lambda l: l.split("  ", 1)[1])
        (folder / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ar.mkdir(parents=True, exist_ok=True)  # also in a clone without stored documents
    card, lic = archive_card(st, ns, name)
    if plan:
        rows = ["| File | Original SHA-256 | Published SHA-256 | What was replaced |", "|---|---|---|---|"]
        for f in files:
            if f["redacted"]:
                rows.append("| `%s` | `%s` | `%s` | %s |" % (f["path"], f["sha256"], f["published_sha256"], f["redaction_note"]))
        (ar / "REDACTIONS.md").write_text("# Redacted access tokens\n\nThese stored pages carried live access tokens that the source site embeds in its own scripts. "
                                         "In the published copy each token is replaced with `%s`; nothing else in the file changed. "
                                         "The original hash identifies the exact page as it was served.\n\n%s\n"
                                         % (PLACEHOLDER.decode(), "\n".join(rows)), encoding="utf-8")
    (ar / "README.md").write_text(card, encoding="utf-8")
    with open(ar / "FILES.csv", "w", encoding="utf-8", newline="") as fh:  # the archive's own index of what is here
        cols = ["path", "record_id", "role", "status", "replaced_by", "replaced_on", "quoted", "url", "retrieved_at",
                "sha256", "published_sha256", "redacted"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for f in sorted((f for f in files if f["in_archive_dataset"]), key=lambda f: f["path"]):
            w.writerow(f)
    (ar / "LICENSE.md").write_text(lic, encoding="utf-8")

    # space
    (sp / "assets").mkdir(parents=True)
    (sp / "data").mkdir()
    shutil.copy2(ROOT / "index.html", sp / "index.html")
    shutil.copy2(ROOT / "robots.txt", sp / "robots.txt")          # its Sitemap: line is what the Space serves
    shutil.copy2(ROOT / "sitemap.xml", sp / "sitemap.xml")
    (sp / "records").mkdir()                                        # the static record pages, one per instrument
    pages = {"index.html"} | {"%s.html" % r["slug"] for r in db["records"] if r.get("slug")}
    for name in sorted(pages):  # only the pages build.py writes, never sync copies such as "page 2.html"
        if (ROOT / "records" / name).is_file():
            shutil.copy2(ROOT / "records" / name, sp / "records" / name)
    for f in (ROOT / "assets").iterdir():
        if f.is_file() and f.name != "site-config.js" and not SYNC_COPY.search(f.name):
            shutil.copy2(f, sp / "assets" / f.name)
    for f in ("records.js", "records.json", "records.csv"):
        shutil.copy2(ROOT / "data" / f, sp / "data" / f)
    excluded = sorted(f["path"] for f in files if f["path"] and not f["in_archive_dataset"])
    redacted = {f["path"]: f["redaction_note"] for f in files if f["redacted"]}
    config = {"archiveBase": repo_url + "-archive/blob/main/", "archiveExcluded": excluded, "archiveRedacted": redacted,
              "datasetUrl": repo_url, "archiveDatasetUrl": repo_url + "-archive", "repoUrl": github_url}
    (sp / "assets" / "site-config.js").write_text(
        "/* Written by tools/publish_hf.py for the Hugging Face Space. */\nwindow.SITE_CONFIG = %s;\n"
        % json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")
    (sp / "README.md").write_text(space_card(ns, name, github_url), encoding="utf-8")
    return st


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0")))


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def previous_release(ns, name):
    """What is published now: version, record IDs and number of history events (from the dataset's raw files)."""
    from huggingface_hub import hf_hub_download
    repo = "%s/%s" % (ns, name)
    try:
        prev = json.load(open(hf_hub_download(repo, "raw/records.json", repo_type="dataset", force_download=True), encoding="utf-8"))
    except Exception as e:  # nothing published yet
        print("No published records.json found (%s); treating this as the first release." % type(e).__name__)
        return {"version": None, "ids": set(), "n_history": 0}
    try:
        with open(hf_hub_download(repo, "raw/history.jsonl", repo_type="dataset", force_download=True), encoding="utf-8") as f:
            n_hist = sum(1 for line in f if line.strip())
    except Exception:
        n_hist = 0
    return {"version": (prev.get("meta") or {}).get("version"), "ids": {r["id"] for r in prev.get("records") or []},
            "n_history": n_hist}


def changes_section(version, prev, events):
    """'Changes in this version' for the dataset card, from the history events added since the last release."""
    new = events[prev["n_history"]:]
    kinds = Counter(e.get("event") for e in new)
    recs = sorted({e.get("record_id") for e in new if e.get("record_id")})
    fields = Counter(e.get("field") for e in new if e.get("event") == "changed")
    if not new:
        body = "No record changed since version %s; this release updates the tools or the documentation." % prev["version"]
    else:
        parts = ["%d %s" % (n, k) for k, n in sorted(kinds.items())]
        body = ("Since version %s: %s, in %d record(s): %s. Fields changed: %s. Every event, with its reason and evidence, "
                "is in the `history` table and in `HISTORY.md`.") % (
            prev["version"] or "-", ", ".join(parts), len(recs), ", ".join(recs[:40]) + (" ..." if len(recs) > 40 else ""),
            ", ".join("%s (%d)" % kv for kv in fields.most_common()) or "none")
    return "\n## Changes in version %s\n\n%s\n" % (version, body)


def release_checks(db, st, out, ns, name, prev, api):
    """Problems that block a release; an empty list means go."""
    problems = []
    meta = db.get("meta") or {}
    version = str(meta.get("version") or "")
    tag = "v" + version
    # main, clean and pushed
    rc, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        problems.append("the checked-out branch is %r, not main" % branch)
    rc, dirty = git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        problems.append("tracked files have uncommitted changes:\n    " + dirty.replace("\n", "\n    "))
    git("fetch", "-q", "origin")
    rc1, head = git("rev-parse", "HEAD")
    rc2, remote = git("rev-parse", "origin/main")
    if head != remote:
        problems.append("main is not identical to origin/main; push or pull first")
    # version
    if prev["version"] and version_tuple(version) <= version_tuple(prev["version"]):
        problems.append("meta.version %s is not higher than the published version %s" % (version, prev["version"]))
    rc, local_tag = git("tag", "--list", tag)
    rc, remote_tag = git("ls-remote", "--tags", "origin", tag)
    if local_tag or remote_tag:
        problems.append("git tag %s already exists" % tag)
    for rid, rtype in (("%s/%s" % (ns, name), "dataset"), ("%s/%s-archive" % (ns, name), "dataset"), ("%s/%s" % (ns, name), "space")):
        try:
            if tag in [t.name for t in api.list_repo_refs(rid, repo_type=rtype).tags]:
                problems.append("%s %s already has the tag %s" % (rtype, rid, tag))
        except Exception:
            pass  # a repository that does not exist yet has no tags
    # records are never deleted
    missing_ids = sorted(prev["ids"] - {r["id"] for r in db["records"]})
    if missing_ids:
        problems.append("%d published record(s) are missing: %s" % (len(missing_ids), ", ".join(missing_ids[:20])))
    # history
    events = history.load()
    bad = [i for i, e in enumerate(events, 1) if [k for k in history.KEYS if k not in e] or e.get("event") not in history.EVENTS]
    if bad:
        problems.append("data/history.jsonl has %d malformed line(s)" % len(bad))
    if len(events) < prev["n_history"]:
        problems.append("data/history.jsonl has fewer events (%d) than the published one (%d); it is append-only"
                        % (len(events), prev["n_history"]))
    # stored files
    if st["missing"]:
        problems.append("%d stored file(s) are missing on this machine" % st["missing"])
    changed = []
    for r in db["records"]:
        for f in (r.get("local_copy") or {}).get("files") or []:
            pth = ROOT / (f.get("path") or "")
            if not f.get("stale") and pth.is_file() and hashlib.sha256(pth.read_bytes()).hexdigest() != f.get("sha256"):
                changed.append(f["path"])
    if changed:
        problems.append("%d stored file(s) no longer match their hash, e.g. %s" % (len(changed), changed[0]))
    # no live tokens in what is published
    live = [str(p.relative_to(out)) for p in (out / "archive").rglob("*")
            if p.is_file() and p.suffix.lower() in (".html", ".htm", ".txt", ".json", ".xml", ".js") and live_tokens(p.read_bytes())]
    if live:
        problems.append("live access tokens in the built archive: %s" % ", ".join(live[:5]))
    # the archive only grows: a release never deletes a file, so the build has to list every file published so far
    try:
        remote = {f for f in api.list_repo_files("%s/%s-archive" % (ns, name), repo_type="dataset")
                  if f.startswith(("archive/", "docs/")) and not f.endswith("SHA256SUMS")}
        built = {str(p.relative_to(out / "archive")) for p in (out / "archive").rglob("*") if p.is_file()}
        lost = sorted(remote - built)
        if lost:
            problems.append("%d file(s) on the archive dataset are not in this build, so FILES.csv would not list them "
                            "(a release never deletes): %s" % (len(lost), ", ".join(lost[:5])))
    except Exception as e:  # a repository that does not exist yet has no files
        if "RepositoryNotFound" not in type(e).__name__:
            problems.append("could not list the archive dataset's files (%s)" % type(e).__name__)
    # a token that can write to all three repositories
    try:
        tok = (api.whoami().get("auth") or {}).get("accessToken") or {}
        repos = ["%s/%s" % (ns, name), "%s/%s-archive" % (ns, name), "%s/%s" % (ns, name)]
        cannot = token_cannot_write(tok, ns, repos)
        if cannot:
            problems.append("the Hugging Face token %r cannot write to %s; use a token with write access to the "
                            "dataset, the archive and the Space" % (tok.get("displayName") or "", ", ".join(sorted(set(cannot)))))
    except Exception as e:
        problems.append("no usable Hugging Face token (%s)" % type(e).__name__)
    return problems


def token_cannot_write(tok, ns, repos):
    """The repositories a token cannot write to. Classic tokens: role 'write' or 'admin' writes everywhere. Fine-grained
    tokens: a write permission scoped to the namespace (user or organisation) or to the repository itself."""
    role = tok.get("role")
    if role in ("write", "admin"):
        return []
    if role != "fineGrained":
        return list(repos)
    fg = tok.get("fineGrained") or {}
    writes = lambda perms: any(x.endswith(".write") and x.startswith("repo") for x in perms or [])  # noqa: E731
    if writes(fg.get("global")):
        return []
    out = []
    for repo in repos:
        ok = False
        for sc in fg.get("scoped") or []:
            ent = sc.get("entity") or {}
            if writes(sc.get("permissions")) and ent.get("name") in (ns, repo):
                ok = True
        if not ok:
            out.append(repo)
    return out


def push(out, ns, name, private, only=("dataset", "archive", "space"), squash_archive=False, label=None):
    from huggingface_hub import HfApi
    api = HfApi()
    ds_id, ar_id, sp_id = "%s/%s" % (ns, name), "%s/%s-archive" % (ns, name), "%s/%s" % (ns, name)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    if label:
        stamp = "%s, %s" % (label, stamp)
    if "dataset" in only:
        api.create_repo(ds_id, repo_type="dataset", private=private, exist_ok=True)
        api.upload_folder(repo_id=ds_id, repo_type="dataset", folder_path=str(out / "dataset"),
                          commit_message="Publish register data (%s)" % stamp,
                          delete_patterns=["data/*", "raw/*", "docs/*"])
        print("uploaded", ds_id)
    if "archive" in only:
        api.create_repo(ar_id, repo_type="dataset", private=private, exist_ok=True)
        api.upload_folder(repo_id=ar_id, repo_type="dataset", folder_path=str(out / "archive"),
                          commit_message="Publish stored source documents (%s)" % stamp)  # adds and updates, never deletes
        api.update_repo_settings(ar_id, repo_type="dataset", gated="auto")
        print("uploaded", ar_id, "(gated, automatic approval)")
        if squash_archive:
            api.super_squash_history(repo_id=ar_id, repo_type="dataset",
                                     commit_message="Stored source documents (history squashed %s)" % stamp)
            print("squashed the history of", ar_id)
    if "space" in only:
        api.create_repo(sp_id, repo_type="space", space_sdk="static", private=private, exist_ok=True)
        api.upload_folder(repo_id=sp_id, repo_type="space", folder_path=str(out / "space"),
                          commit_message="Publish web app (%s)" % stamp,
                          delete_patterns=["assets/*", "data/*", "records/*"])
        print("uploaded", sp_id)
    return ds_id, ar_id, sp_id


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publish the register to Hugging Face.")
    ap.add_argument("--namespace", default="kelkalot")
    ap.add_argument("--name", default="every-ai-policy-ever")
    ap.add_argument("--github", default="https://github.com/kelkalot/every-ai-policy-ever")
    ap.add_argument("--out", default=str(ROOT / "dist" / "hf"))
    ap.add_argument("--push", action="store_true", help="upload to Hugging Face after building")
    ap.add_argument("--only", default="dataset,archive,space", help="comma-separated subset to upload: dataset, archive, space")
    ap.add_argument("--squash-archive", action="store_true", help="rewrite the archive dataset's history into one commit")
    ap.add_argument("--private", action="store_true", help="create the repos as private (existing repos keep their visibility)")
    ap.add_argument("--release", action="store_true", help="publish main as version meta.version, after the release checks, and tag it")
    ap.add_argument("--dry-run", action="store_true", help="with --release: run the checks and stop before uploading")
    args = ap.parse_args(argv)
    out = Path(args.out)
    if args.release:
        return release(args, out)
    st = build_all(out, args.namespace, args.name, args.github)
    print("Built %s: %d records; archive %d of %d stored files (%.0f MB), %d third-party copies left out, "
          "%d with access tokens replaced, %d missing on this machine." % (out, st["n"], st["pub_files"], st["files"],
                                                                          st["pub_mb"], st["excluded"], st["redacted"], st["missing"]))
    only = [x.strip() for x in args.only.split(",") if x.strip()]
    if args.push and "archive" in only and st["missing"]:
        # the archive upload deletes remote files that are not present here, so a clone without archive/ would empty it
        raise SystemExit("Not uploading the archive: %d stored files are missing on this machine. Publish the archive only "
                         "from the machine that holds archive/, or leave it out with --only dataset,space." % st["missing"])
    if args.push:
        push(out, args.namespace, args.name, args.private, [x.strip() for x in args.only.split(",") if x.strip()],
             squash_archive=args.squash_archive)
    return 0


def release(args, out):
    from huggingface_hub import HfApi
    api = HfApi()
    db = build.normalise(build.load())
    version = str((db.get("meta") or {}).get("version") or "")
    tag = "v" + version
    prev = previous_release(args.namespace, args.name)
    # the gate (tools/gate.py, AGENTS.md section 7.10): every change since the last release, with the stored documents
    rc, last = git("describe", "--tags", "--abbrev=0", "--match", "v*", "HEAD")
    gate = subprocess.run([sys.executable, str(ROOT / "tools" / "gate.py"), "--quiet", "--base",
                           last.strip() if rc == 0 and last.strip() else "origin/main"], cwd=str(ROOT))
    if gate.returncode:
        print("\nNot releasing: the gate failed (above). Fix what it reports, merge, and release again.")
        return 1
    changes = changes_section(version, prev, history.load())
    st = build_all(out, args.namespace, args.name, args.github, changes_md=changes)
    print("Release %s (published now: %s). Built %s: %d records, archive %d files, %d third-party copies left out, "
          "%d with tokens replaced." % (tag, prev["version"] or "nothing", out, st["n"], st["pub_files"], st["excluded"], st["redacted"]))
    print(changes.strip())
    problems = release_checks(db, st, out, args.namespace, args.name, prev, api)
    # tests of the built files themselves: tables, archive hashes, Space, history replay, credentials, the app
    tests = subprocess.run([sys.executable, str(ROOT / "tools" / "release_check.py"), "--out", str(out)], cwd=str(ROOT))
    if tests.returncode:
        problems.append("the release tests failed (above): python3 tools/release_check.py --out %s" % out)
    if problems:
        print("\nNot releasing:")
        for p in problems:
            print("  - " + p)
        return 1
    print("\nAll release checks passed.")
    if args.dry_run:
        print("Dry run: nothing uploaded, nothing tagged.")
        return 0
    ids = push(out, args.namespace, args.name, False, ("dataset", "archive", "space"), label="Release " + tag)
    msg = "Release %s: %d records. %s" % (tag, st["n"], changes.strip().split("\n")[-1][:400])
    for rid, rtype in ((ids[0], "dataset"), (ids[1], "dataset"), (ids[2], "space")):
        api.create_tag(rid, tag=tag, tag_message=msg, repo_type=rtype)
        print("tagged %s %s as %s" % (rtype, rid, tag))
    rc, out_ = git("tag", "-a", tag, "-m", msg)
    rc2, out2 = git("push", "origin", tag)
    print("git tag %s %s" % (tag, "created and pushed" if rc == 0 and rc2 == 0 else "FAILED: %s %s" % (out_, out2)))
    return 0 if rc == 0 and rc2 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
