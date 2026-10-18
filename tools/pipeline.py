#!/usr/bin/env python3
"""The scripts of the pipeline in AGENTS.md sections 5 to 7. Agents do the reading and judging;
this file does the bookkeeping, so that a run can be repeated and checked.

    python3 tools/pipeline.py new --type discover --scope "region:Europe" [--tool T --model M]
    python3 tools/pipeline.py new --type refresh [--scope "ids:EU-03,US-09"]     # default: the queue
    python3 tools/pipeline.py new --type recheck --scope "region:Oceania"
    python3 tools/pipeline.py status   --run RUN
    python3 tools/pipeline.py stage    --run RUN --stage extract --tool "Claude Code" --model M
    python3 tools/pipeline.py dedupe   --run RUN     # number candidates, drop duplicates, update the frame
    python3 tools/archive.py --run RUN --browser     # (the archiver) store the candidates' sources
    python3 tools/pipeline.py textify  --run RUN     # a .txt with [page N] markers next to every stored file
    python3 tools/pipeline.py evidence --run RUN     # check quotes and hashes, compute levels, flag rule breaches
    python3 tools/pipeline.py sample   --run RUN     # pick the blind double-extraction sample
    python3 tools/pipeline.py compare  --run RUN     # field agreement between the two extractions
    python3 tools/pipeline.py assemble --run RUN     # runs/RUN/pass.json for tools/merge.py
    python3 tools/pipeline.py report   --run RUN     # runs/RUN/report.md
    python3 tools/pipeline.py queue [--days 180] [--limit 25]
    python3 tools/pipeline.py frame --due [--days 180] | --report | --add CODE --name N --level L --region R
    python3 tools/pipeline.py hosts [--code C] [--pending]        # the curated list of official sites
    python3 tools/pipeline.py questions [--sync] [--apply] [--dry-run]   # open questions as GitHub issues
    python3 tools/pipeline.py intake [--dry-run]     # suggestions and provided documents from GitHub issues
    python3 tools/pipeline.py intake --triage        # undecided suggestions with warning signs; changes nothing
    python3 tools/pipeline.py leads [--add --lead T --cell C|--code C [--issued-by B]|--record ID
                                     --url U --seen-in U --why W --by NAME [--provided FILE]]
                                    [--attach L001 --provided FILE --by NAME] [--drop L001 --why W --by NAME]
    python3 tools/pipeline.py hosts --add HOST --code C --status official|"not official"|proposed --by NAME
                                    [--operator O --kind K --evidence-url U --quote Q --note N]
    python3 tools/pipeline.py log-human --run RUN --id ID --result ok|problem --note "..." [--by NAME]
    python3 tools/pipeline.py log-scope --id ID --decision in|out --note "..." [--by NAME] [--run RUN]

Files of a run, all under runs/RUN/ (AGENTS.md section 5.1):
  run.json              type, scope, groups of frame cells or record IDs, tool and model per stage
  candidates/<g>.json   collectors' output, one file per group
  search-log.jsonl      one line per frame cell searched
  candidates.json       written by dedupe: every candidate with a status; active ones are C001, C002, ...
  sources.json          written by tools/archive.py --run: the stored files per candidate
  texts.json            written by textify: the text file, hash and page count of every stored file
  extractions/<c>.json, extractions-blind/<c>.json, checks/<c>.json    the agents' output
  evidence.json, sample.json, agreement.json, pass.json, report.md     written here

Standard library only (Python 3.8+). PDFs need pypdf or poppler's pdftotext; scans need tesseract.
"""
import argparse
import datetime as dt
import difflib
import hashlib
import json
import math
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, OrderedDict, defaultdict
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import history  # noqa: E402
import publish_hf  # noqa: E402  (its list of third-party hosts)
import validate  # noqa: E402

ROOT = build.ROOT
RUNS = ROOT / "runs"
FRAME = ROOT / "pipeline" / "frame.json"
REQUESTS = ROOT / "pipeline" / "refresh-requests.jsonl"
SITES = ROOT / "pipeline" / "official-sites.json"
SITE_STATUSES = ["official", "not official", "proposed"]
SCOPE_DECISIONS = ROOT / "pipeline" / "scope-decisions.md"

RUN_TYPES = ["discover", "refresh", "recheck", "compare"]
FACT_FIELDS = ["title", "original_title", "issuing_body", "official_identifier", "date_published", "date_in_force",
               "date_last_updated", "status", "legal_force"]
LEVEL_FIELDS = ["title", "date_published", "status"]   # date_published only counts when it is not null
SOURCE_KINDS = ["official", "alt-official", "secondary"]
DECISIONS = ["record", "update", "duplicate", "out-of-scope", "needs-human"]
VERDICTS = ["supported", "unsupported", "contradicted", "judgment-differs"]
OVERALL = ["accept", "accept-with-fixes", "needs-human", "reject"]
METHOD_TOKENS = {"A": "official-url-fetched", "B": "alternative-official-url-fetched", "C": "search-confirmed"}
RECORD_FIELDS = ["id", "slug", "title", "original_title", "short_title", "jurisdiction", "country", "jurisdiction_level",
                 "region", "issuing_body", "instrument_type", "legal_force", "status", "date_published", "date_in_force",
                 "date_last_updated", "official_identifier", "official_url", "secondary_url", "language", "summary",
                 "safety_topics", "related", "notes", "scope_note", "english_version", "verification"]
SET_BY_SCRIPT = {"id", "slug"}
IN_FORCE = {"In force", "Partially in force"}
ENDED = {"Superseded", "Revoked / withdrawn", "Lapsed"}
CURRENT = IN_FORCE | ENDED | {"Published (non-binding, current)"}  # statuses a passed in-force date does not contradict
QUOTE_MAX = 300
QUOTE_MIN_ALNUM = 8   # a quote needs at least this many letters or digits to identify a passage ("2026" is not enough)
# Which stored files can count as official evidence. The archiver sets a file's role; an agent only labels its quotes,
# so a label is capped by the role and by the host the file came from.
SECONDARY_ROLES = {"secondary"}
# Addresses that usually hold an announcement about an instrument rather than its text (AGENTS.md section 5.4): a
# quote labelled official from such a page gets a warning, and the extractor and the checker decide. Statements and
# declarations that are themselves the instrument are often published on such pages too, so this only warns.
ANNOUNCEMENT_URL = re.compile("|".join([
    r"/news(?:room)?\b", r"news-and-updates", r"news-events", r"press-?releases?", r"pressreleaseview", r"/press/",
    r"media-?releases?", r"/media-cent(?:er|re)/", r"fact-?sheets?", r"briefing-room", r"statements-releases",
    r"/speeches?/", r"/blog/", r"announce", r"/aktuelt/", r"/nyheter/", r"/frettir/", r"/berita/", r"/noticias?/",
    r"/actualites/", r"/aktuelles?/", r"siaran", r"prezly\.com", r"/articles?/", r"/20\d\d/\d\d/\d\d/",
    r"/gia/general/", r"/bbs/", r"/briefing/",
]), re.I)
GOV_HOST = re.compile(r"\.(gov|mil|int)$|(^|\.)(gov|gob|gouv|govt|gv|go|gub|mil|admin|gc|leg)\.[a-z]{2,3}$"
                      r"|\.state\.[a-z]{2}\.us$"
                      r"|(^|\.)(europa\.eu|un\.org|unesco\.org|oecd\.org|oecd\.ai|wto\.org|asean\.org)$")
NOT_OFFICIAL_HOSTS = set(publish_hf.THIRD_PARTY_HOSTS)
SUMMARY_MIN, SUMMARY_MAX = 250, 700
TOPICS_MIN, TOPICS_MAX = 2, 6
STALE_DAYS = 180
PROCESS_PATTERNS = [
    r"\bfetch(?:ed|ing)?\b", r"\b(?:could|can) ?not be (?:fetched|confirmed|verified|retrieved|reached|downloaded|found)\b",
    r"\bwas not (?:confirmed|verified|fetched)\b", r"\bnot (?:been )?(?:confirmed|verified) (?:on|from|against)\b",
    r"\bas (?:reported|summari[sz]ed)\b", r"\breported(?:ly)? to (?:include|cover|contain)\b", r"\bHTTP \d{3}\b",
    r"\brobots\.txt\b", r"\bweb search\b", r"\bsearch budget\b", r"\bthe researcher\b", r"\bthis (?:machine|session)\b",
    r"\b(?:law[- ]firm|counsel)'?s? (?:summary|summaries|analysis|note)\b", r"\bbot[- ]check\b",
    r"\bAGENTS\.md\b", r"\bscope[- ]decisions?\b", r"\binclusive default\b", r"\binclude[- ]and[- ]flag\b",
    r"\bthe (?:extractor|checker|collector|coordinator)\b",
]
STAGES = ["collect", "extract", "blind", "check"]

# What a run kicks off, in order: (step, who does it, what to run or which role to follow). `new` writes the list into
# run.json and prints it; `status` shows which steps are done. Agents work through the steps of their run only.
_FIND = [("extract", "extractors, about 8 candidates each", "pipeline/roles/extract.md -> extractions/<ID>.json; for "
                                                          "extra_urls the coordinator (not the extractor) archives and "
                                                          "textifies again, then sends the candidates back once"),
         ("evidence", "script", "python3 tools/pipeline.py evidence --run {run}"),
         ("sample", "script", "python3 tools/pipeline.py sample --run {run}"),
         ("blind", "a fresh extractor", "pipeline/roles/extract.md -> extractions-blind/<ID>.json; never opens extractions/"),
         ("agreement", "script", "python3 tools/pipeline.py compare --run {run}"),
         ("check", "the checker, in a fresh context", "pipeline/roles/check.md -> checks/<ID>.json"),
         ("assemble", "script", "python3 tools/pipeline.py assemble --run {run}"),
         ("merge", "script", "python3 tools/merge.py runs/{run}/pass.json --dry-run, then without --dry-run; "
                             "python3 tools/build.py"),
         ("report", "script", "python3 tools/pipeline.py report --run {run}; frame --report; questions --sync; intake"),
         ("gate", "script", "python3 tools/gate.py: every change against the rules; fix what fails, never skip it"),
         ("commit", "coordinator", "one commit on the branch run/{run}")]
_STORE = [("archive", "script", "python3 tools/archive.py --run {run} --browser"),
          ("textify", "script", "python3 tools/pipeline.py textify --run {run}")]
STEPS = {
    "discover": [("collect", "collectors, one per group", "pipeline/roles/collect.md -> candidates/<group>.json, "
                                                                     "search-log.jsonl"),
                 ("dedupe", "script", "python3 tools/pipeline.py dedupe --run {run}")] + _STORE + _FIND,
    "refresh": _STORE + _FIND,
    "recheck": _STORE + _FIND,
    "compare": [("textify", "script", "python3 tools/definitions.py textify --run {run}"),
                ("extract", "an extractor", "pipeline/roles/compare.md -> definitions/<ID>.json"),
                ("blind", "a fresh extractor", "pipeline/roles/compare.md -> definitions-blind/<ID>.json; never opens definitions/"),
                ("quotes", "script", "python3 tools/definitions.py check --run {run}"),
                ("agreement", "script", "python3 tools/definitions.py compare --run {run}"),
                ("check", "the checker, in a fresh context", "pipeline/roles/compare.md -> checks/<ID>.json"),
                ("merge", "script", "python3 tools/definitions.py merge --run {run}; python3 tools/build.py"),
                ("report", "script", "python3 tools/definitions.py report --run {run}"),
                ("gate", "script", "python3 tools/gate.py: every change against the rules; fix what fails, never skip it"),
                ("commit", "coordinator", "one commit on the branch run/{run}")],
}


def run_steps(run):
    return [{"step": a, "who": b, "do": c.format(run=run["run_id"])} for a, b, c in STEPS[run["type"]]]


def step_done(d, run, step):
    """True when the files a step writes are there, False when not, None when no file shows it."""
    if run["type"] == "compare":
        recs = set((read_json(d / "plan.json", {}) or {}).get("records") or [])
        files = {"textify": "texts.json", "quotes": "check.json", "agreement": "agreement.json", "report": "report.md"}
        if step in files:
            return (d / files[step]).is_file()
        if step in ("extract", "blind", "check"):
            sub = {"extract": "definitions", "blind": "definitions-blind", "check": "checks"}[step]
            return bool(recs) and recs <= set(agent_files(d, sub))
        if step == "merge":
            seen = (read_json(ROOT / "data" / "definitions.json", {}) or {}).get("compared") or {}
            return any(v.get("run_id") == run["run_id"] for v in seen.values())
        return None
    act = [c["cand_id"] for c in candidates(d) if c.get("status") == "active"]
    ex = agent_files(d, "extractions")
    files = {"dedupe": "candidates.json", "archive": "sources.json", "textify": "texts.json", "evidence": "evidence.json",
             "sample": "sample.json", "agreement": "agreement.json", "assemble": "pass.json", "report": "report.md"}
    if step == "collect":
        return bool(run.get("groups")) and all((d / "candidates" / ("%s.json" % g)).is_file() for g in run["groups"])
    if step in files:
        return (d / files[step]).is_file()
    if step == "extract":
        return bool(act) and set(act) <= set(ex)
    if step == "blind":
        want = (read_json(d / "sample.json", {}) or {}).get("blind") or []
        return bool(want) and set(want) <= set(agent_files(d, "extractions-blind"))
    if step == "check":
        need = [c for c, e in ex.items() if (e or {}).get("decision") in ("record", "update")]
        return bool(need) and set(need) <= set(agent_files(d, "checks"))
    if step == "merge":
        return any(e.get("run_id") == run["run_id"] for e in history.load())
    return None


def print_steps(d, run, marks=True):
    for i, st in enumerate(run.get("steps") or run_steps(run), 1):
        mark = {True: "[x] ", False: "[ ] ", None: "    "}[step_done(d, run, st["step"])] if marks else ""
        print("  %s%2d. %-10s %-34s %s" % (mark, i, st["step"], st["who"], st["do"]))


# ----------------------------------------------------------------------------- small helpers

def today():
    return dt.date.today().isoformat()


def read_json(path, default=None):
    path = Path(path)
    if not path.is_file():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def rel(p):
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def slugify(s, n=60):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:n].rstrip("-")) or "x"


def norm_title(t):
    return " ".join(re.findall(r"\w+", (t or "").casefold()))


def norm_url(u):
    if not u:
        return ""
    p = urllib.parse.urlsplit(u.strip())
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = urllib.parse.unquote(p.path).rstrip("/")
    return host + path + (("?" + p.query) if p.query else "")


def sha256_file(path, _cache={}):
    path = Path(path)
    key = (str(path), path.stat().st_mtime, path.stat().st_size)
    if key not in _cache:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _cache[key] = h.hexdigest()
    return _cache[key]


def run_path(run_id):
    d = RUNS / run_id
    if not (d / "run.json").is_file():
        raise SystemExit("No run %r: runs/%s/run.json is missing. Create one with: python3 tools/pipeline.py new" % (run_id, run_id))
    return d


def load_run(run_id):
    d = run_path(run_id)
    return d, read_json(d / "run.json")


def save_run(d, run):
    write_json(d / "run.json", run)


def load_db():
    return build.normalise(build.load())


def candidates(d):
    return (read_json(d / "candidates.json", {}) or {}).get("candidates") or []


def active(d):
    return [c for c in candidates(d) if c.get("status") == "active"]


def agent_files(d, sub):
    out = {}
    folder = d / sub
    if folder.is_dir():
        for p in sorted(folder.glob("*.json")):
            try:
                out[p.stem] = read_json(p)
            except ValueError as e:
                out[p.stem] = {"_error": "not valid JSON: %s" % e}
    return out


def parse_date(s):
    try:
        return dt.date.fromisoformat(str(s)) if s and validate.FULL_DATE.match(str(s)) else None
    except ValueError:
        return None


# ----------------------------------------------------------------------------- frame

def load_frame():
    f = read_json(FRAME)
    if not f:
        raise SystemExit("pipeline/frame.json is missing")
    return f


def save_frame(f):
    write_json(FRAME, f)


def strip_www(host):
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def load_sites(path=SITES):
    """pipeline/official-sites.json, the curated list of sites (AGENTS.md section 7.6). Every entry says who runs the
    host, how that was established and who decided; entries are never deleted, so a decision is not undone later."""
    data = read_json(path, None) or {"about": "", "sites": []}
    problems, seen = [], set()
    for i, e in enumerate(data.get("sites") or []):
        key = (e.get("code"), strip_www(e.get("host")))
        if not all(key):
            problems.append("entry %d needs code and host" % (i + 1))
        if e.get("status") not in SITE_STATUSES:
            problems.append("%s %s: status must be one of %s" % (key + (", ".join(SITE_STATUSES),)))
        if e.get("status") in ("official", "not official") and not (e.get("decided_by") and e.get("decided_on")):
            problems.append("%s %s: a decision needs decided_by and decided_on" % key)
        if key in seen:
            problems.append("%s %s is listed twice" % key)
        seen.add(key)
    if problems:
        raise SystemExit("pipeline/official-sites.json: " + "; ".join(problems[:10]))
    return data


def site_hosts(data):
    """(code -> hosts that count as official, hosts that never count as official)."""
    official, rejected = defaultdict(list), set()
    for e in data.get("sites") or []:
        if e["status"] == "official":
            official[e["code"]].append(strip_www(e["host"]))
        elif e["status"] == "not official":
            rejected.add(strip_www(e["host"]))
    return official, rejected


def frame_cells(f):
    for j in f["jurisdictions"]:
        for t, cell in j["cells"].items():
            yield j, t, cell


def frame_names(_cache=[]):
    if not _cache:
        try:
            _cache.append({j["name"] for j in load_frame()["jurisdictions"]})
        except SystemExit:
            _cache.append(set())
    return _cache[0]


def cell_id(j, t):
    return "%s/%s" % (j["code"], t)


def select_frame(f, scope, days):
    """Resolve a discover scope to frame cells. Selectors (space-separated, combined with AND):
    region:<text>  codes:FI,SE  level:National  types:legislature,gazette  due  all"""
    toks = shlex.split(scope or "")
    if not toks:
        raise SystemExit("A discover run needs --scope, e.g. 'region:Europe', 'codes:FI,SE,NO', 'due', 'all'")
    regions, codes, levels, types, due = [], set(), [], set(), False
    for t in toks:
        k, _, v = t.partition(":")
        k = k.lower()
        if k == "region":
            regions.append(v.casefold())
        elif k == "codes":
            codes |= {x.strip().upper() for x in v.split(",") if x.strip()}
        elif k == "level":
            levels.append(v.casefold())
        elif k == "types":
            types |= {x.strip() for x in v.split(",") if x.strip()}
        elif k == "due":
            due = True
        elif k == "all":
            pass
        else:
            raise SystemExit("Unknown scope selector %r; use region:, codes:, level:, types:, due or all" % t)
    known = {j["code"] for j in f["jurisdictions"]}
    unknown = sorted(codes - known)
    if unknown:
        raise SystemExit("Not in pipeline/frame.json: %s. Add them with: pipeline.py frame --add" % ", ".join(unknown))
    out = []
    for j, t, cell in frame_cells(f):
        if regions and not any(r in j["region"].casefold() for r in regions):
            continue
        if codes and j["code"] not in codes:
            continue
        if levels and not any(l in j["level"].casefold() for l in levels):
            continue
        if types and t not in types:
            continue
        if due and not cell_due(cell, days):
            continue
        out.append(cell_id(j, t))
    return out


def cell_due(cell, days):
    d = parse_date(cell.get("last_searched"))
    return d is None or (dt.date.today() - d).days >= days


def group_cells(f, cells, size=10):
    """Groups of about `size` jurisdictions, by region, for parallel collectors."""
    by_j = OrderedDict()
    for c in cells:
        by_j.setdefault(c.split("/")[0], []).append(c)
    region = {j["code"]: j["region"] for j in f["jurisdictions"]}
    by_region = OrderedDict()
    for code, cs in by_j.items():
        by_region.setdefault(region.get(code, "Other"), []).append(cs)
    groups = OrderedDict()
    for reg, lists in by_region.items():
        n = max(1, math.ceil(len(lists) / size))
        for i in range(n):
            chunk = lists[i * size:(i + 1) * size]
            name = slugify(reg, 30) + ("-%d" % (i + 1) if n > 1 else "")
            groups[name] = [c for cs in chunk for c in cs]
    return groups


def cmd_frame(args):
    f = load_frame()
    days = args.days or f.get("stale_days", STALE_DAYS)
    if args.add:
        if any(j["code"] == args.add for j in f["jurisdictions"]):
            raise SystemExit("%s is already in the frame" % args.add)
        if not (args.name and args.level and args.region):
            raise SystemExit("--add needs --name, --level and --region")
        if args.region not in validate.VOCAB["region"] or args.level not in validate.VOCAB["jurisdiction_level"]:
            raise SystemExit("--region and --level must use the register's vocabulary")
        types = {"National": ["legislature", "gazette", "executive", "ministries", "ai-bodies", "elections", "supervisors"],
                 "Supranational": ["legislature", "gazette", "executive", "ai-bodies", "supervisors"],
                 "Sub-national": ["legislature", "gazette", "executive", "ministries", "supervisors"],
                 "International": ["repository"]}[args.level]
        f["jurisdictions"].append({"code": args.add, "name": args.name, "level": args.level, "region": args.region,
                                   "parent": args.parent, "records": 0,
                                   "cells": {t: {"last_searched": None, "outcome": None, "run_id": None,
                                                 "where_to_look": []} for t in types}})
        save_frame(f)
        print("Added %s (%s) with %d cells." % (args.add, args.name, len(types)))
        return 0
    if args.report:
        text = coverage_report(f, days)
        out = ROOT / "pipeline" / "coverage.md"
        out.write_text(text, encoding="utf-8")
        print(text.split("\n\n")[1])
        print("Written to %s" % rel(out))
        return 0
    cells = [cell_id(j, t) for j, t, c in frame_cells(f) if cell_due(c, days)]
    print("%d of %d cells are due (never searched, or not for %d days)." % (
        len(cells), sum(1 for _ in frame_cells(f)), days))
    if args.due:
        by_region = Counter(j["region"] for j, t, c in frame_cells(f) if cell_due(c, days))
        for reg, n in by_region.most_common():
            print("  %-28s %d" % (reg, n))
    return 0


def coverage_report(f, days):
    rows = defaultdict(lambda: [0, 0, 0, 0])  # cells, searched ever, searched recently, jurisdictions with records
    never = []
    for j in f["jurisdictions"]:
        r = rows[j["region"]]
        r[3] += 1 if j.get("records") else 0
        any_search = False
        for t, c in j["cells"].items():
            r[0] += 1
            if c.get("last_searched"):
                r[1] += 1
                any_search = True
                if not cell_due(c, days):
                    r[2] += 1
        if not any_search:
            never.append(j)
    total = [sum(r[i] for r in rows.values()) for i in range(4)]
    lines = ["# Search coverage", "",
             "Written %s by tools/pipeline.py frame --report from pipeline/frame.json: %d jurisdictions, %d cells; "
             "%d cells searched by the pipeline, %d of them within %d days." % (
                 today(), len(f["jurisdictions"]), total[0], total[1], total[2], days), "",
             "| Region | Cells | Searched | Within %d days | Jurisdictions with records |" % days, "|---|---:|---:|---:|---:|"]
    for reg in sorted(rows):
        r = rows[reg]
        lines.append("| %s | %d | %d | %d | %d |" % (reg, r[0], r[1], r[2], r[3]))
    lines += ["", "## Never searched by the pipeline (%d)" % len(never), ""]
    lines += ["- %s %s (%s)%s" % (j["code"], j["name"], j["region"], ", %d record(s) from earlier research" % j["records"]
                                  if j.get("records") else "") for j in never]
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- new, status, stage

def select_records(db, scope):
    toks = shlex.split(scope or "")
    R = db["records"]
    ids = None
    for t in toks:
        k, _, v = t.partition(":")
        k = k.lower()
        if k == "ids":
            want = [x.strip() for x in v.split(",") if x.strip()]
            missing = [x for x in want if x not in {r["id"] for r in R}]
            if missing:
                raise SystemExit("No such record(s): %s" % ", ".join(missing))
            ids = want
        elif k == "region":
            R = [r for r in R if v.casefold() in r["region"].casefold()]
        elif k == "codes":
            codes = {x.strip().upper() for x in v.split(",") if x.strip()}
            R = [r for r in R if re.sub(r"-\d+$", "", r["id"]) in codes or r["id"].split("-")[0] in codes]
        elif k == "level":
            R = [r for r in R if v.casefold() in r["jurisdiction_level"].casefold()]
        elif k == "all":
            pass
        else:
            raise SystemExit("Unknown scope selector %r for records; use ids:, region:, codes:, level: or all" % t)
    if ids is not None:
        return ids
    return [r["id"] for r in R]


def run_size_ok(args, n):
    """Refuse a run larger than MAX_RUN before anything is written."""
    if n > MAX_RUN[args.type] and not getattr(args, "large", False):
        raise SystemExit("This run would take %d %s; one run takes at most %d. Narrow the scope (one region, a list of "
                         "codes or IDs) or split it into several runs; --large overrides." % (
                             n, "frame cells" if args.type == "discover" else "records", MAX_RUN[args.type]))


def cmd_new(args):
    if args.type not in RUN_TYPES:
        raise SystemExit("--type must be one of %s" % ", ".join(RUN_TYPES))
    label = args.label or args.scope or ("leads" if getattr(args, "leads", None) else
                                         "queue" if args.type == "refresh" else "all")
    base = "%s-%s-%s" % (today(), args.type, slugify(label, 32))
    run_id, n = base, 2
    while (RUNS / run_id).exists():
        run_id, n = "%s-%d" % (base, n), n + 1
    d = RUNS / run_id
    run = OrderedDict([("run_id", run_id), ("type", args.type), ("scope", args.scope or None), ("started", today()),
                       ("coordinator", {"tool": args.tool, "model": args.model}),
                       ("stages", {s: {"tool": None, "model": None, "date": None} for s in STAGES}),
                       ("status", None)])
    db = load_db()
    if args.type == "discover" and getattr(args, "leads", None):
        # a leads run follows up known leads only; its cells are where each lead belongs, and they are not marked
        # as searched, because nobody searched them as a whole
        f = load_frame()
        lead_file = Path(args.leads)
        lead_reg = read_json(lead_file, {}) or {}
        leads = lead_reg.get("leads") or []
        if any("state" in l for l in leads):  # the leads registry: take only the queued leads
            leads = [l for l in leads if l.get("state") == "queued"]
            if not leads:
                raise SystemExit("No queued leads in %s" % args.leads)
        known = {cell_id(j, t) for j, t, c in frame_cells(f)}
        bad = [l.get("cell") for l in leads if l.get("cell") not in known]
        if not leads or bad:
            raise SystemExit("--leads needs {\"leads\": [{\"lead\", \"cell\", ...}]} with frame cells; unknown: %s"
                             % ", ".join(map(str, bad[:10])))
        cells = sorted({l["cell"] for l in leads})
        run_size_ok(args, len(cells))
        run["mode"] = "leads"
        run["leads"] = leads
        if any("state" in l for l in lead_reg.get("leads") or []):
            for l in leads:
                l.update(state="in-run", run_id=run_id)
            write_json(lead_file, lead_reg)
        run["cells"] = cells
        run["groups"] = group_cells(f, cells, args.group_size)
    elif args.type == "discover":
        f = load_frame()
        cells = select_frame(f, args.scope, args.days or f.get("stale_days", STALE_DAYS))
        if not cells:
            raise SystemExit("The scope selects no frame cells.")
        run_size_ok(args, len(cells))
        run["cells"] = cells
        run["groups"] = group_cells(f, cells, args.group_size)
        run["status"] = "collecting"
        # the queued leads of the selected cells go with the run, so that its collectors follow them up as well
        lead_reg = read_json(LEADS, {}) or {}
        taken = [l for l in lead_reg.get("leads") or [] if l.get("state") == "queued" and l.get("cell") in set(cells)]
        if taken:
            for l in taken:
                l.update(state="in-run", run_id=run_id)
            run["leads"] = taken
            write_json(LEADS, lead_reg)
    elif args.type == "compare":
        import definitions as D  # noqa: E402  (same folder; it imports this module)
        if args.scope:
            ids, reasons = select_records(db, args.scope), {}
        else:
            due = D.compare_queue(db)
            ids, reasons = [rid for rid, _ in due][:args.limit or 5], dict(due)
        if not ids:
            raise SystemExit("The scope selects no records." if args.scope else "No record is due for a compare run.")
        run_size_ok(args, len(ids))
        run["record_ids"] = ids
        run["reasons"] = {rid: reasons.get(rid) or ["named in the scope"] for rid in ids}
        run["status"] = "textify"
        write_json(d / "plan.json", {"about": "Compare run: the definitions layer of the crosswalk (issue #70).",
                                     "records": ids, "term_groups": D.DEFAULT_GROUPS, "ocr_lang": {}})
    else:
        if args.type == "refresh" and not args.scope:
            due = queue(db, args.days or STALE_DAYS)
            ids = [rid for rid, _ in due][:args.limit or 25]
            reasons = dict(due)
        else:
            ids = select_records(db, args.scope or "all")
            reasons = {}
        if not ids:
            raise SystemExit("The scope selects no records.")
        run_size_ok(args, len(ids))
        by = {r["id"]: r for r in db["records"]}
        run["record_ids"] = ids
        run["status"] = "archiving"
        cands = [{"cand_id": rid, "record_id": rid, "status": "active", "title_as_found": by[rid]["title"],
                  "url": by[rid].get("official_url"), "why": "; ".join(reasons.get(rid, [])) or args.type}
                 for rid in ids]
        write_json(d / "candidates.json", {"run_id": run_id, "generated": today(), "candidates": cands})
    subs = ("definitions", "definitions-blind", "checks") if args.type == "compare" else \
        ("candidates", "extractions", "extractions-blind", "checks")
    for sub_ in subs:
        (d / sub_).mkdir(parents=True, exist_ok=True)
    run["steps"] = run_steps(run)
    save_run(d, run)
    print("Created runs/%s" % run_id)
    if args.type == "discover":
        print("%d cells in %d groups: %s" % (len(run["cells"]), len(run["groups"]),
                                             ", ".join("%s (%d)" % (g, len(c)) for g, c in run["groups"].items())))
    else:
        print("%d records: %s" % (len(run["record_ids"]), ", ".join(run["record_ids"])))
    print("This run kicks off these steps, in order (also in run.json; `pipeline.py status --run %s` shows which "
          "are done). Record who runs each agent step with `pipeline.py stage`:" % run_id)
    print_steps(d, run, marks=False)
    print(run_id)
    return 0


# the size of one run, unless --large: a run that fits in one session and one subscription's usage window
MAX_RUN = {"discover": 120, "refresh": 40, "recheck": 40, "compare": 15}  # frame cells, or records


def cmd_menu(args):
    """What is ready to run now, one line each with the command that starts it, and what only people decide."""
    import definitions as D  # noqa: E402  (same folder; it imports this module)
    import importlib.util
    db, f = load_db(), load_frame()
    print("Every AI Policy Ever: work that is ready now. Pick one; one run per session.")
    print("Read the pinned issue Project status first: the maintainers' priorities and what is in progress "
          "(gh issue list --label status, or python3 tools/pipeline.py board).\n")
    have = sum(1 for r in db["records"] for x in (r.get("local_copy") or {}).get("files") or []
               if x.get("path") and (ROOT / x["path"]).is_file())
    setup = []
    if not have:
        setup.append("No stored documents (a fresh clone has no archive/): run `python3 tools/archive.py --browser` once, "
                     "or download kelkalot/every-ai-policy-ever-archive from Hugging Face. Refresh, recheck and compare "
                     "runs read them.")
    for mod, why in (("pypdf", "reads PDFs"), ("playwright", "the browser retry for blocked pages")):
        if importlib.util.find_spec(mod) is None:
            setup.append("Python package %s is missing (%s): python3 -m pip install %s" % (mod, why, mod))
    if not shutil.which("tesseract"):
        setup.append("tesseract is missing (OCR for scanned PDFs); runs work without it but cannot read scans")
    if not any(shutil.which(t) for t in ("textutil", "antiword", "catdoc", "soffice", "libreoffice")):
        setup.append("no reader for .doc files (antiword, catdoc or LibreOffice; macOS has textutil); runs work without "
                     "it but cannot quote stored Word documents")
    if setup:
        print("Setup first:")
        for x in setup:
            print("  - " + x)
        print()
    refresh = queue(db, STALE_DAYS)
    urgent = [rid for rid, why in refresh if any(w.startswith(("requested", "date_in_force")) for w in why)]
    leads = [l for l in (read_json(LEADS, {}) or {}).get("leads") or [] if l.get("state") == "queued"]
    due_cells = select_frame(f, "due", f.get("stale_days", STALE_DAYS))
    by_region = Counter(next(j["region"] for j in f["jurisdictions"] if j["code"] == c.split("/")[0]) for c in due_cells)
    compare = D.compare_queue(db)
    opts = [
        ("decisions", "Apply the maintainers' decisions from GitHub (always first; reads GitHub, quick)",
         "python3 tools/pipeline.py intake && python3 tools/pipeline.py questions --apply", True),
        ("refresh", "Refresh run: %d records due%s; one run takes the top 25" % (
            len(refresh), (", %d of them urgent (news or a passed in-force date)" % len(urgent)) if urgent else ""),
         "/run-pipeline refresh", bool(refresh)),
        ("leads", "Leads run: %d queued leads (suggestions people accepted)" % len(leads),
         "/run-pipeline discover leads", bool(leads)),
        ("discover", "Discover run: %d frame cells due; pick one region, about 10 jurisdictions (%s)" % (
            len(due_cells), ", ".join("%s %d" % (k, v) for k, v in by_region.most_common(4))),
         '/run-pipeline discover <region or countries>', bool(due_cells)),
        ("compare", "Compare run: %d records due for the definitions layer; one run takes the top 5" % len(compare),
         "/run-pipeline compare", bool(compare)),
    ]
    print("For agents (Claude Code: /run-pipeline ...; Codex: $run-pipeline ...):")
    for i, (key, text, cmd, ready) in enumerate([o for o in opts if o[3]], 1):
        print("  %d. %-9s %s\n               %s" % (i, key, text, cmd))
    if urgent:
        print("\nSuggested: the decisions, then a refresh run (%d urgent records)." % len(urgent))
    elif leads:
        print("\nSuggested: the decisions, then the leads run.")
    qs = [q for q in (read_json(QUESTIONS, {}) or {}).get("questions") or [] if q.get("state") == "open"]
    kinds = Counter(q.get("kind") for q in qs)
    sites = (read_json(SITES, {}) or {}).get("sites") or []
    print("\nFor people only (agents never decide these; AGENTS.md sections 7.6 to 7.8):")
    print("  - %d open questions on GitHub (%s)" % (len(qs), ", ".join("%d %s" % (v, k) for k, v in kinds.most_common())))
    print("  - %d hosts to review (`python3 tools/pipeline.py hosts --pending`)" % sum(
        1 for x in sites if x.get("status") == "proposed" or x.get("decided_by") == "seed"))
    print("  - documents a site blocks, to download and provide: see archive/needs-attention.txt and the "
          "Provide a document form")
    print("\nA run does only the steps `pipeline.py new` prints (also in its run.json). Flow chart: pipeline/flow.md")
    return 0


BOARD_TITLE = "Project status"
PRIORITIES = re.compile(r"<!-- priorities -->\n?(.*?)\n?<!-- /priorities -->", re.S)
PRIORITIES_EMPTY = ("_No priorities written yet. A maintainer writes them here, in this section only; agents suggest "
                    "changes in a comment._")


def run_summary(d):
    """(start date, type, status, one line) of a run folder."""
    run = read_json(d / "run.json", {}) or {}
    plan = read_json(d / "plan.json", {}) or {}
    kind = run.get("type") or ("compare" if plan.get("term_groups") else "host review" if (d / "hosts").is_dir() else "?")
    rep = (d / "report.md").read_text(encoding="utf-8") if (d / "report.md").is_file() else ""
    line = next((l[2:] for l in rep.splitlines() if l.startswith("- Added:")), "")
    if not line:
        m = re.search(r"\*\*Repeatability:\*\* (.*?)\.", rep)
        n = len([x for x in (read_json(ROOT / "data" / "definitions.json", {}) or {}).get("definitions") or []
                 if x.get("run_id") == d.name])
        line = "%d definitions merged%s" % (n, ("; " + m.group(1)) if m else "") if plan else ""
    return run.get("started") or d.name[:10], kind, run.get("status") or ("reported" if rep else "open"), line


def days_ago(date):
    try:
        return (dt.date.today() - dt.date.fromisoformat(str(date)[:10])).days
    except ValueError:
        return None


def board_markdown(priorities=None, live=True):
    """The body of the pinned Project status issue, from the repository (and GitHub when live)."""
    import definitions as D  # noqa: E402  (same folder; it imports this module)
    db, f = load_db(), load_frame()
    meta, recs = db.get("meta") or {}, db["records"]
    repo = github_repo()
    head = git_out("log", "-1", "--format=%h|%s", "HEAD").strip().split("|", 1)
    L = ["# %s" % BOARD_TITLE, "",
         "**Updated %s UTC** from main at `%s` (%s)." % (
             dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), head[0], head[1] if len(head) > 1 else ""), "",
         "Generated by `python3 tools/pipeline.py board` from the repository%s. Everything except **Priorities now** "
         "is rewritten after every merge to main, every release and every Monday, so do not edit it; AGENTS.md section "
         "7.11 says how agents use this issue." % (" and GitHub" if live else ""), ""]
    # the register
    tags = sorted([t for t in git_out("tag", "--list", "v*").split() if re.match(r"v\d+(\.\d+)*$", t)],
                  key=lambda t: [int(x) for x in t[1:].split(".")])
    last = tags[-1] if tags else None
    last_date = git_out("log", "-1", "--format=%cs", last).strip() if last else None
    lv = Counter((r.get("verification") or {}).get("level") for r in recs)
    defs = (read_json(ROOT / "data" / "definitions.json", {}) or {}).get("definitions") or []
    since = [e for e in history.load() if last_date and (e.get("date") or "") > last_date]
    L += ["## The register", "",
          "- **Data version %s**, %d records (level A %d, B %d, C %d), %d definitions." % (
              meta.get("version"), len(recs), lv.get("A", 0), lv.get("B", 0), lv.get("C", 0), len(defs)),
          "- **Last release:** %s%s; %d history event(s) since." % (
              last or "none", (" on %s" % last_date) if last_date else "", len(since)), ""]
    # priorities: the one section maintainers write
    L += ["## Priorities now", "", "<!-- priorities -->", (priorities or PRIORITIES_EMPTY).strip(), "<!-- /priorities -->", ""]
    # in progress
    L += ["## In progress", ""]
    prs = json.loads(gh("pr", "list", "--repo", repo, "--state", "open", "--json", "number,title,headRefName") or "[]") if live else []
    in_pr = {p["headRefName"] for p in prs}
    branches = [b.strip().replace("origin/", "", 1) for b in git_out("branch", "-r", "--no-merged", "origin/main").splitlines()
                if b.strip().startswith("origin/run/")]
    items = ["- #%d %s (`%s`)" % (p["number"], p["title"], p["headRefName"]) for p in prs]
    items += ["- `%s`: a run branch not merged and without a pull request" % b for b in branches if b not in in_pr]
    L += (items or ["- Nothing open."]) + ["", "Do not start a run whose scope overlaps one listed here.", ""]
    # rhythm
    def when(d):  # the last commit that touched the run folder, else its modification time
        t = git_out("log", "-1", "--format=%ct", "--", "runs/%s" % d.name).strip()
        return int(t) if t else int(d.stat().st_mtime)
    runs = [run_summary(d) + (d.name,) for d in sorted((d for d in RUNS.iterdir() if d.is_dir()), key=when, reverse=True)]
    def last_of(*kinds):
        x = next((r for r in runs if r[1] in kinds), None)
        return (x[0], x[4]) if x else (None, None)
    archived = max((x.get("retrieved_at") or "" for r in recs for x in (r.get("local_copy") or {}).get("files") or []), default="")[:10]
    rows = [("Archiver (stores changed sources)", "weekly", archived or None, None, 7),
            ("Full recheck of the register", "monthly", *last_of("recheck"), None),
            ("Refresh run", "between rechecks", *last_of("refresh"), 14),
            ("Discover run", "quarterly", *last_of("discover"), 92),
            ("Compare run", "as the queue allows", *last_of("compare"), 31),
            ("Release", "after merged runs", last_date, last, 31)]
    L += ["## Rhythm", "", "| What | How often | Last | |", "|---|---|---|---|"]
    # the monthly recheck covers the register only when every record was checked by a run in the last 31 days
    kinds = {d.name: (read_json(d / "run.json", {}) or {}).get("type") for d in RUNS.iterdir() if d.is_dir()}
    fresh = {e["record_id"] for e in history.load()
             if kinds.get(e.get("run_id")) in ("recheck", "refresh") and e.get("event") in ("changed", "re-verified")
             and (days_ago(e.get("date")) if days_ago(e.get("date")) is not None else 99) <= 31}  # today is 0 days ago
    for what, often, date, rid, limit in rows:
        n = days_ago(date) if date else None
        state = "never" if date is None else ("due" if n is not None and limit and n > limit else "ok")
        if limit is None:  # the full recheck: how much of the register a run checked in the last 31 days
            done = len(fresh & {r["id"] for r in recs})
            state = "ok" if done == len(recs) else "%d of %d records checked in the last 31 days" % (done, len(recs))
        if what == "Release" and since:
            state = "%d change(s) not released yet" % len(since)
        L.append("| %s | %s | %s%s | %s |" % (what, often, date or "-", (" (%s)" % rid) if rid else "", state))
    L += [""]
    # queues
    refresh = queue(db, STALE_DAYS)
    urgent = [rid for rid, why in refresh if any(w.startswith(("requested", "date_in_force")) for w in why)]
    leads = [l for l in (read_json(LEADS, {}) or {}).get("leads") or [] if l.get("state") == "queued"]
    due_cells = select_frame(f, "due", f.get("stale_days", STALE_DAYS))
    compare = D.compare_queue(db, on_disk=False)
    L += ["## Queues", "",
          "- Refresh: %d records due%s." % (len(refresh), (", %d urgent (%s)" % (len(urgent), ", ".join(urgent[:8]))) if urgent else ""),
          "- Leads: %d queued." % len(leads),
          "- Discover: %d of %d frame cells due (never searched, or not for %d days)." % (
              len(due_cells), sum(1 for _ in frame_cells(f)), f.get("stale_days", STALE_DAYS)),
          "- Compare: %d records due." % len(compare),
          "", "`python3 tools/pipeline.py menu` turns these into commands.", ""]
    # for people
    qs = [q for q in (read_json(QUESTIONS, {}) or {}).get("questions") or [] if q.get("state") == "open"]
    kinds = Counter(q.get("kind") for q in qs)
    sites = (read_json(SITES, {}) or {}).get("sites") or []
    weak = sum(1 for r in recs if (r.get("local_copy") or {}).get("status") in ("archived-review", "partial", "failed"))
    L += ["## For people", "",
          "- [%d open questions](https://github.com/%s/issues?q=is%%3Aissue+is%%3Aopen+label%%3Aquestion): %s." % (
              len(qs), repo, ", ".join("%d %s" % (v, k) for k, v in kinds.most_common()) or "none"),
          "- %d hosts to review (`python3 tools/pipeline.py hosts --pending`)." % sum(
              1 for x in sites if x.get("status") == "proposed" or x.get("decided_by") == "seed"),
          "- %d records whose stored copy needs attention (a bot-check page, a partial or failed download); a "
          "provided document often fixes it." % weak, ""]
    # enhancements and their trackers
    L += ["## Enhancements", ""]
    issues = json.loads(gh("issue", "list", "--repo", repo, "--state", "open", "--label", "enhancement", "--limit", "50",
                           "--json", "number,title,body") or "[]") if live else []
    for i in sorted(issues, key=lambda x: x["number"]):
        body = i.get("body") or ""
        done, todo = len(re.findall(r"(?m)^\s*- \[[xX]\]", body)), re.findall(r"(?m)^\s*- \[ \] (.+)$", body)
        nxt = re.sub(r"[*`]", "", todo[0])[:110] if todo else ("all done" if done else "no task list in the issue")
        L.append("- #%d %s: %d of %d tasks done; next: %s" % (i["number"], i["title"], done, done + len(todo), nxt))
    L += [] if issues else ["- " + ("None open." if live else "(GitHub not read)")]
    L += ["", "## Last runs (most recently changed first)", "", "| Run | Type | Status | Result |", "|---|---|---|---|"]
    for date, kind, status, line, name in runs[:8]:
        L.append("| [%s](https://github.com/%s/tree/main/runs/%s) | %s | %s | %s |" % (name, repo, name, kind, status, line or "-"))
    L += ["", AGENT_MARK]
    return "\n".join(L) + "\n"


def git_out(*args):
    return subprocess.run(["git", "-C", str(ROOT)] + list(args), capture_output=True, text=True).stdout


def cmd_board(args):
    """Print the project status, or (--sync) write it into the pinned Project status issue."""
    if not args.sync:
        print(board_markdown(live=bool(shutil.which("gh")) and not args.offline))
        return 0
    repo = github_repo()
    if not can_write(repo):
        return not_a_maintainer(repo, "board --sync")
    found = json.loads(gh("issue", "list", "--repo", repo, "--state", "open", "--label", "status", "--limit", "5",
                          "--json", "number,title,body") or "[]")
    found = [i for i in found if i["title"] == BOARD_TITLE]
    old = found[0] if found else None
    m = PRIORITIES.search((old or {}).get("body") or "")
    body = board_markdown(priorities=m.group(1) if m and m.group(1).strip() else None)
    if args.dry_run:
        print(body)
        return 0
    if old:
        gh("issue", "edit", str(old["number"]), "--repo", repo, "--body-file", "-", input_text=body)
        print("Updated #%d %s" % (old["number"], BOARD_TITLE))
        return 0
    gh("label", "create", "status", "--repo", repo, "--color", "0E8A16", "--description",
       "The pinned project status, written by tools/pipeline.py board", "--force")
    url = gh("issue", "create", "--repo", repo, "--title", BOARD_TITLE, "--label", "status", "--body-file", "-",
             input_text=body).strip()
    num = url.rstrip("/").rsplit("/", 1)[-1]
    pin = subprocess.run(["gh", "issue", "pin", num, "--repo", repo], capture_output=True, text=True)
    print("Created %s%s" % (url, "" if pin.returncode == 0 else " (could not pin it: %s)" % pin.stderr.strip()))
    return 0


def cmd_stage(args):
    d, run = load_run(args.run)
    if args.stage not in STAGES:
        raise SystemExit("--stage must be one of %s" % ", ".join(STAGES))
    run["stages"][args.stage] = dict({"tool": args.tool, "model": args.model, "date": today()},
                                     **({"tokens": args.tokens} if args.tokens else {}))
    save_run(d, run)
    print("Recorded %s: %s, %s%s" % (args.stage, args.tool, args.model, (", %d tokens" % args.tokens) if args.tokens else ""))
    return 0


def cmd_status(args):
    d, run = load_run(args.run)
    cands = candidates(d)
    act = [c for c in cands if c.get("status") == "active"]
    ex, bl, ch = agent_files(d, "extractions"), agent_files(d, "extractions-blind"), agent_files(d, "checks")
    sample = read_json(d / "sample.json", {}) or {}
    ev = read_json(d / "evidence.json", {}) or {}
    texts = read_json(d / "texts.json", {}) or {}
    logs = read_log(d)
    print("Run %s (%s), started %s, status: %s" % (run["run_id"], run["type"], run["started"], run.get("status")))
    print("Steps:")
    print_steps(d, run)
    if run["type"] == "compare":
        plan = read_json(d / "plan.json", {}) or {}
        print("Records: %s" % ", ".join(plan.get("records") or []))
        for s in STAGES[1:]:
            st = run["stages"].get(s) or {}
            print("  %-8s %s" % (s, ("%s, %s, %s" % (st.get("tool"), st.get("model"), st.get("date"))) if st.get("tool") else "-"))
        return 0
    for s in STAGES:
        st = run["stages"].get(s) or {}
        print("  %-8s %s" % (s, ("%s, %s, %s" % (st.get("tool"), st.get("model"), st.get("date"))) if st.get("tool") else "-"))
    if run["type"] == "discover":
        print("Cells: %d; logged: %d; group files: %d" % (len(run.get("cells") or []), len({l.get("cell") for l in logs}),
                                                      len(list((d / "candidates").glob("*.json")))))
    print("Candidates: %d (%d active)" % (len(cands), len(act)))
    print("Sources stored: %d; texts: %d" % (len(read_json(d / "sources.json", {}) or {}), len(texts.get("files") or [])))
    todo_ex = [c["cand_id"] for c in act if c["cand_id"] not in ex]
    print("Extractions: %d of %d%s" % (len([c for c in act if c["cand_id"] in ex]), len(act),
                                      ("; missing: " + ", ".join(todo_ex[:30])) if todo_ex else ""))
    if sample.get("blind"):
        print("Blind sample: %d of %d done" % (len([c for c in sample["blind"] if c in bl]), len(sample["blind"])))
    need_check = [c for c, e in ex.items() if (e or {}).get("decision") in ("record", "update")]
    print("Checks: %d of %d" % (len([c for c in need_check if c in ch]), len(need_check)))
    if ev:
        print("Evidence: %d with errors" % len([c for c, r in (ev.get("extractions") or {}).items() if r.get("errors")]))
    print("pass.json: %s; report.md: %s" % ("yes" if (d / "pass.json").is_file() else "no",
                                          "yes" if (d / "report.md").is_file() else "no"))
    return 0


# ----------------------------------------------------------------------------- dedupe

def read_log(d):
    out = []
    p = d / "search-log.jsonl"
    if p.is_file():
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    print("WARNING  search-log.jsonl line %d is not valid JSON; skipped" % n)
    return out


def cmd_dedupe(args):
    d, run = load_run(args.run)
    if run["type"] != "discover":
        raise SystemExit("dedupe is for discover runs; refresh and recheck runs start with their records")
    if agent_files(d, "extractions") and not args.force:
        raise SystemExit("Extractions exist already; renumbering would break them. Use --force only if you mean it.")
    db = load_db()
    R = db["records"]
    by_url, by_title = {}, {}
    for r in R:
        for u in (r.get("official_url"), r.get("secondary_url")):
            if u:
                by_url.setdefault(norm_url(u), r["id"])
        for t in (r.get("title"), r.get("short_title"), r.get("original_title")):
            if t and len(norm_title(t)) > 12:
                by_title.setdefault(norm_title(t), r["id"])
    old = {(c.get("group"), c.get("cand_ref")): c.get("cand_id") for c in candidates(d)}
    out, seen_url, seen_title = [], {}, {}
    requests = []
    n = max([int(c[1:]) for c in old.values() if c and re.match(r"^C\d+$", c)] + [0])
    files = sorted((d / "candidates").glob("*.json"))
    if not files:
        raise SystemExit("No collector output in runs/%s/candidates/" % args.run)
    for p in files:
        doc = read_json(p) or {}
        group = doc.get("group") or p.stem
        for i, c in enumerate(doc.get("candidates") or [], 1):
            c = dict(c)
            c["group"] = group
            c.setdefault("cand_ref", "%s-%02d" % (group, i))
            c.setdefault("collector", {"tool": doc.get("tool"), "model": doc.get("model")})
            nu, nt = norm_url(c.get("url")), norm_title(c.get("title_as_found"))
            hit = (by_url.get(nu) if nu else None) or (by_title.get(nt) if len(nt) > 12 else None)
            dup = c.get("possible_duplicate_of")
            if dup and dup in {r["id"] for r in R}:
                c["status"] = "refresh-request"
                c["record_id"] = dup
                requests.append({"date": today(), "run_id": args.run, "record_id": dup, "why": c.get("why"),
                                 "url": c.get("url")})
            elif hit:
                c["status"] = "in-register"
                c["record_id"] = hit
            elif nu and nu in seen_url:
                c["status"], c["duplicate_of"] = "duplicate-in-run", seen_url[nu]
            elif len(nt) > 12 and nt in seen_title:
                c["status"], c["duplicate_of"] = "duplicate-in-run", seen_title[nt]
            elif c.get("scope_guess") == "out":
                c["status"] = "out-of-scope"
            else:
                c["status"] = "active"
            if c["status"] == "active":
                cid = old.get((group, c["cand_ref"]))
                if not cid:
                    n += 1
                    cid = "C%03d" % n
                c["cand_id"] = cid
                if nu:
                    seen_url[nu] = cid
                if len(nt) > 12:
                    seen_title[nt] = cid
            else:
                c["cand_id"] = None
            out.append(c)
    if requests:
        REQUESTS.parent.mkdir(parents=True, exist_ok=True)
        with open(REQUESTS, "a", encoding="utf-8") as fh:
            for r in requests:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    logs = read_log(d)
    logged = {l.get("cell") for l in logs}
    missing = [c for c in run.get("cells") or [] if c not in logged]
    f = load_frame()
    cells = {cell_id(j, t): (j, cell) for j, t, cell in frame_cells(f)}
    unknown = []
    for l in logs:
        hit = cells.get(l.get("cell"))
        if not hit:
            unknown.append(l.get("cell"))
            continue
        j, cell = hit
        if run.get("mode") != "leads":  # a leads run did not search the cell as a whole
            cell.update({"last_searched": l.get("date") or today(), "outcome": l.get("outcome"), "run_id": args.run})
        for u in l.get("new_portals") or []:
            if u not in cell["where_to_look"]:
                cell["where_to_look"].append(u)
    save_frame(f)
    write_json(d / "candidates.json", {"run_id": args.run, "generated": today(), "candidates": out,
                                       "cells_without_log": missing, "unknown_cells": sorted(set(unknown) - {None})})
    run["status"] = "archiving"
    save_run(d, run)
    st = Counter(c["status"] for c in out)
    print("Candidates: %s" % ", ".join("%s %d" % kv for kv in st.most_common()))
    if requests:
        print("%d existing record(s) added to the refresh requests (pipeline/refresh-requests.jsonl)." % len(requests))
    if missing:
        print("WARNING  %d cell(s) in scope have no search-log line: %s" % (len(missing), ", ".join(missing[:20])))
    if unknown:
        print("WARNING  search-log names cells that are not in the frame: %s" % ", ".join(sorted(set(unknown) - {None})[:20]))
    print("Frame updated from %d log line(s). Next: python3 tools/archive.py --run %s --browser" % (len(logs), args.run))
    return 0


# ----------------------------------------------------------------------------- textify

class _Blocks(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "header", "footer", "h1", "h2",
             "h3", "h4", "h5", "h6", "dt", "dd", "blockquote", "pre", "hr", "td", "th", "main", "nav", "aside"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "template", "svg"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template", "svg") and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _tidy(text):
    lines = [re.sub(r"[ \t\u00a0]+", " ", l).strip() for l in text.splitlines()]
    out, blank = [], 0
    for l in lines:
        if l:
            out.append(l)
            blank = 0
        elif not blank:
            out.append("")
            blank = 1
    return "\n".join(out).strip()


def _html_fragment_text(html):
    p = _Blocks()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    return "".join(p.parts)


_NEXT_SKIP = {"script", "style", "link", "meta", "noscript", "template", "svg", "path", "title", "head"}
_SVG_PATH = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9.,\s-]+$")


def _flight_rows(payload):
    """Rows of a React Server Components payload: ("T", text) for text rows, ("J", json) for the others."""
    pos, n, row = 0, len(payload), re.compile(r"([0-9a-f]+):")
    while pos < n:
        m = row.match(payload, pos)
        if not m:
            nl = payload.find("\n", pos)
            if nl < 0:
                break
            pos = nl + 1
            continue
        pos = m.end()
        if payload.startswith("T", pos) and "," in payload[pos:pos + 12]:
            comma = payload.find(",", pos)
            try:
                size = int(payload[pos + 1:comma], 16)
            except ValueError:
                size = 0
            raw = payload[comma + 1:comma + 1 + size * 4].encode("utf-8")[:size].decode("utf-8", "ignore")
            yield "T", raw
            pos = comma + 1 + len(raw)
        else:
            nl = payload.find("\n", pos)
            end = n if nl < 0 else nl
            yield "J", payload[pos:end]
            pos = end + 1


def _flight_walk(node, out):
    """Text of a React element tree as the payload stores it (["$", tag, key, props]), in document order."""
    if isinstance(node, str):
        if node.startswith("$$"):
            out.append(node[1:])
        elif not node.startswith("$"):
            out.append(node)
    elif isinstance(node, list):
        if len(node) == 4 and node[0] == "$" and isinstance(node[1], str):
            tag, props = node[1], node[3] if isinstance(node[3], dict) else {}
            if tag in _NEXT_SKIP:
                return
            block = tag in _Blocks.BLOCK
            if block:
                out.append("\n")
            inner = props.get("dangerouslySetInnerHTML")
            if isinstance(inner, dict) and isinstance(inner.get("__html"), str):
                out.append(_html_fragment_text(inner["__html"]))
            _flight_walk(props.get("children"), out)
            if block:
                out.append("\n")
        else:
            for x in node:
                _flight_walk(x, out)
    elif isinstance(node, dict) and "children" in node:
        _flight_walk(node["children"], out)


def _json_strings(node, out):
    """Prose in the page props of an older Next.js page (__NEXT_DATA__): strings with words, HTML converted."""
    if isinstance(node, str):
        if re.search(r"<(p|div|h\d|li|br|span|strong|em|table)\b", node):
            out.append("\n" + _html_fragment_text(node) + "\n")
        elif " " in node.strip() and re.search(r"[^\W\d_]{2}", node) and not node.startswith(("http", "/")):
            out.append(node + "\n")
    elif isinstance(node, list):
        for x in node:
            _json_strings(x, out)
    elif isinstance(node, dict):
        for x in node.values():
            _json_strings(x, out)


def nextjs_text(html):
    """Text a Next.js page keeps in its script data instead of its HTML: the App Router payload
    (self.__next_f.push) or the older __NEXT_DATA__ props. Finlex statutes and IMDA articles are stored this way;
    the browser draws them from this data, so the plain HTML holds only the page frame. Empty for other pages."""
    out = []
    pushes = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    if pushes:
        try:
            payload = "".join(json.loads('"' + p + '"') for p in pushes)
        except ValueError:
            payload = ""
        for kind, row in _flight_rows(payload):
            if kind == "T":
                if re.search(r"<(p|div|h\d|li|br|span|strong|em|table)\b", row):
                    out.append("\n" + _html_fragment_text(row) + "\n")
                elif row.strip() and not _SVG_PATH.match(row.strip()):
                    out.append("\n" + row + "\n")
                continue
            try:
                node = json.loads(row)
            except ValueError:
                continue
            _flight_walk(node, out)
            out.append("\n")
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            _json_strings(((data.get("props") or {}).get("pageProps")), out)
        except ValueError:
            pass
    return _tidy("".join(out))


def html_text(path):
    import archive  # noqa: E402  (same folder; imported late because it is large)
    body = Path(path).read_bytes()
    html = archive.decode_html(body, "text/html")
    text = _tidy(_html_fragment_text(html))
    data = nextjs_text(html)
    if data:
        seen = {l for l in text.splitlines() if l}
        extra = [l for l in data.splitlines() if l and l not in seen]
        if extra:  # only what the page frame does not already show
            return text + "\n\n[page data]\n" + "\n".join(extra), None, "html+page data"
    return text, None, "html"


WORD_EXTS = (".doc", ".docx", ".rtf", ".odt")


def word_text(path):
    """Text of a word-processor file: .docx read directly, the others with a converter if one is installed
    (textutil on macOS, antiword or catdoc for .doc, LibreOffice for all). Returns (text, pages, method, warning)."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".docx":
        import zipfile
        import xml.etree.ElementTree as ET
        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        try:
            with zipfile.ZipFile(path) as z:
                root = ET.fromstring(z.read("word/document.xml"))
            paras = []
            for para in root.iter(w + "p"):
                bits = []
                for el in para.iter():
                    if el.tag == w + "t" and el.text:
                        bits.append(el.text)
                    elif el.tag == w + "tab":
                        bits.append("\t")
                    elif el.tag == w + "br":
                        bits.append("\n")
                paras.append("".join(bits))
            return _tidy("\n".join(paras)), None, "docx", None
        except Exception as e:  # not a valid .docx (some servers label other files so); try the converters
            first_error = str(e)
    else:
        first_error = None
    tools = [["textutil", "-convert", "txt", "-encoding", "UTF-8", "-stdout", str(path)]]
    if ext == ".doc":
        tools += [["antiword", "-w", "0", str(path)], ["catdoc", "-w", "-d", "utf-8", str(path)]]
    for cmd in tools:
        if shutil.which(cmd[0]):
            try:
                res = subprocess.run(cmd, capture_output=True, timeout=120)
            except (OSError, subprocess.SubprocessError):
                continue
            out = res.stdout.decode("utf-8", "replace")
            if res.returncode == 0 and out.strip():
                return _tidy(out), None, cmd[0], None
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if office:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                subprocess.run([office, "--headless", "--convert-to", "txt:Text", "--outdir", tmp, str(path)],
                               capture_output=True, timeout=180)
                outs = list(Path(tmp).glob("*.txt"))
                if outs:
                    return _tidy(outs[0].read_text(encoding="utf-8", errors="replace")), None, "libreoffice", None
            except (OSError, subprocess.SubprocessError):
                pass
    return "", None, None, ("no reader for %s files: install antiword, catdoc or LibreOffice (macOS has textutil)%s"
                            % (ext, "; " + first_error if first_error else ""))


def file_text(src, ocr_lang):
    """Text of one stored file for textify: (text, pages, method, warning)."""
    ext = Path(src).suffix.lower()
    if ext == ".pdf":
        return pdf_text(src, ocr_lang)
    if ext in (".html", ".htm", ".xml"):
        text, _, method = html_text(src)
        return text, None, method, None
    if ext in (".txt", ".json"):
        return Path(src).read_text(encoding="utf-8", errors="replace"), None, "copy", None
    if ext in WORD_EXTS:
        return word_text(src)
    return "", None, None, "no text extraction for %s files" % ext


def garbled_share(pages):
    """Share of non-space characters that are control, unassigned or private-use code points: near 0 for real text,
    high when a PDF's font encoding defeats the extractor (pypdf then returns shifted or random characters)."""
    import unicodedata
    chars = [ch for ch in "".join(pages) if not ch.isspace()]
    bad = sum(1 for ch in chars if unicodedata.category(ch) in ("Cc", "Cn", "Co") or ch == "\ufffd")
    return bad / len(chars) if chars else 0.0


def pdf_text(path, ocr_lang, ocr_pages=60):
    """Text of a PDF with [page N] markers: pypdf, else pdftotext (also when pypdf's text is garbled);
    OCR with tesseract when it is a scan."""
    pages, method, warning, n_pages = [], None, None, 0
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [(pg.extract_text() or "") for pg in reader.pages]
        n_pages, method = len(pages), "pypdf"
    except Exception:
        pages = []
    garbled = pages and garbled_share(pages) > 0.05
    if (not pages or garbled) and shutil.which("pdftotext"):
        try:
            out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, timeout=300)
            alt = out.stdout.decode("utf-8", "replace").split("\f")
            if alt and not alt[-1].strip():
                alt = alt[:-1]
            if alt and (not pages or garbled_share(alt) < garbled_share(pages)):
                pages, n_pages = alt, len(alt)
                method = "pdftotext (pypdf's text was garbled)" if garbled else "pdftotext"
        except Exception:
            pass
    if not pages:
        return "", 0, None, "no PDF text extractor worked (install pypdf, or poppler's pdftotext)"
    chars = sum(len(p.strip()) for p in pages)
    if chars < 80 * len(pages):
        if shutil.which("tesseract") and shutil.which("pdftoppm"):
            ocr = []
            with tempfile.TemporaryDirectory() as tmp:
                for i in range(1, min(n_pages, ocr_pages) + 1):
                    base = Path(tmp) / ("p%d" % i)
                    subprocess.run(["pdftoppm", "-r", "200", "-png", "-f", str(i), "-l", str(i), "-singlefile",
                                    str(path), str(base)], capture_output=True, timeout=300)
                    img = base.with_suffix(".png")
                    res = subprocess.run(["tesseract", str(img), "-", "-l", ocr_lang], capture_output=True,
                                         timeout=300) if img.is_file() else None
                    ocr.append(res.stdout.decode("utf-8", "replace") if res else "")
            if sum(len(p.strip()) for p in ocr) > chars:
                pages, method = ocr, "ocr (tesseract, %s)" % ocr_lang
                if n_pages > ocr_pages:
                    warning = "OCR covers the first %d of %d pages" % (ocr_pages, n_pages)
            else:
                warning = "little text, and OCR found no more"
        else:
            warning = "the PDF has little text (probably a scan) and tesseract or pdftoppm is not installed"
    text = "\n".join("[page %d]\n%s" % (i, p.strip()) for i, p in enumerate(pages, 1))
    return text, len(pages), method, warning


def stored_files(sources, cid):
    """All stored files for a candidate: [(path, sha256, role, url)]."""
    e = sources.get(cid) or {}
    out = []
    lcs = [("main", e.get("main"))] + [("extra", lc) for lc in (e.get("extras") or {}).values()]
    for kind, lc in lcs:
        for f in (lc or {}).get("files") or []:
            role = f.get("role") if kind == "main" else "extra"
            if f.get("path"):
                out.append((f["path"], f.get("sha256"), role, f.get("url")))
            # the snapshot this one replaced is still a stored copy with its hash, and may be what an agent quoted
            if f.get("previous_path") and (ROOT / f["previous_path"]).is_file():
                out.append((f["previous_path"], f.get("previous_sha256"), role, f.get("url")))
    return out


def cmd_textify(args):
    d, run = load_run(args.run)
    sources = read_json(d / "sources.json", {}) or {}
    if not sources:
        raise SystemExit("runs/%s/sources.json is missing; run: python3 tools/archive.py --run %s" % (args.run, args.run))
    old = {t["file"]: t for t in (read_json(d / "texts.json", {}) or {}).get("files") or []}
    rows, done = [], 0
    for cid in sorted(sources):
        for path, digest, role, url in stored_files(sources, cid):
            src = ROOT / path
            if not src.is_file():
                rows.append({"cand_id": cid, "file": path, "sha256": digest, "txt": None, "warning": "file missing"})
                continue
            txt = Path(str(src) + ".txt")
            prev = old.get(path)
            if prev and prev.get("sha256") == digest and txt.is_file() and not args.force:
                rows.append(dict(prev, cand_id=cid))
                continue
            ext = src.suffix.lower()
            pages, method, warning = None, None, None
            try:
                text, pages, method, warning = file_text(src, args.ocr_lang)
            except Exception as e:
                text, warning = "", "text extraction failed: %s" % e
            header = "# Text of %s (sha256 %s), made by tools/pipeline.py textify (%s)\n\n" % (path, digest, method or "-")
            txt.write_text(header + text + "\n", encoding="utf-8")
            done += 1
            rows.append({"cand_id": cid, "file": path, "sha256": digest, "role": role, "url": url, "txt": rel(txt),
                         "pages": pages, "chars": len(text), "method": method, "warning": warning})
    write_json(d / "texts.json", {"run_id": args.run, "generated": today(), "files": rows})
    run["status"] = "extracting"
    save_run(d, run)
    warn = [r for r in rows if r.get("warning")]
    print("Text for %d file(s) (%d new); %d with warnings." % (len(rows), done, len(warn)))
    for r in warn[:30]:
        print("  %-6s %s: %s" % (r["cand_id"], r["file"], r["warning"]))
    print("Extractors read runs/%s/texts.json for the files, hashes and text paths of each candidate." % args.run)
    return 0


# ----------------------------------------------------------------------------- evidence

def norm_text(s):
    s = unicodedata.normalize("NFKC", s or "").replace("­", "")
    s = re.sub(r"[‘’‚‛′`´]", "'", s)
    s = re.sub(r"[“”„‟″«»]", '"', s)
    s = re.sub(r"[‐-―−]", "-", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


def loose(s):
    return "".join(ch for ch in norm_text(s) if ch.isalnum())


class TextIndex:
    """The stored files of one run, with their texts, for quote matching."""

    def __init__(self, d, db):
        self.d = d
        self.sources = read_json(d / "sources.json", {}) or {}
        self.texts = {t["file"]: t for t in (read_json(d / "texts.json", {}) or {}).get("files") or []}
        self.records = {r["id"]: r for r in db["records"]}
        self._cache = {}
        self.cells = {c["cand_id"]: c.get("cell") for c in candidates(d)}
        self.frame_hosts, self.rejected_hosts = site_hosts(load_sites())

    def file_info(self, cid, record_id=None):
        """path -> (archive role, URL it came from) for every file a candidate may quote."""
        out = {p: (role, url) for p, _, role, url in stored_files(self.sources, cid)}
        rid = record_id or (self.sources.get(cid) or {}).get("record_id")
        if rid and rid in self.records:
            for f in (self.records[rid].get("local_copy") or {}).get("files") or []:
                for path in (f.get("path"), f.get("previous_path")):
                    if path:
                        out.setdefault(path, (f.get("role"), f.get("final_url") or f.get("url")))
        return out

    def code_for(self, cid, record_id=None):
        cell = self.cells.get(cid) or ""
        if "/" in cell:
            return cell.split("/")[0]
        rid = record_id or (self.sources.get(cid) or {}).get("record_id") or cid
        return re.sub(r"-\d+$", "", rid or "")

    def files_for(self, cid, record_id=None):
        out = {p: digest for p, digest, _, _ in stored_files(self.sources, cid)}
        rid = record_id or (self.sources.get(cid) or {}).get("record_id")
        if rid and rid in self.records:  # a refresh may quote the record's own stored copies, and the ones they replaced
            for f in (self.records[rid].get("local_copy") or {}).get("files") or []:
                if f.get("path"):
                    out.setdefault(f["path"], f.get("sha256"))
                if f.get("previous_path") and (ROOT / f["previous_path"]).is_file():
                    out.setdefault(f["previous_path"], f.get("previous_sha256"))
        return out

    def pages(self, path):
        if path not in self._cache:
            t = self.texts.get(path)
            p = ROOT / (t["txt"] if t and t.get("txt") else path + ".txt")
            if not p.is_file():
                self._cache[path] = None
            else:
                raw = p.read_text(encoding="utf-8", errors="replace")
                raw = raw.split("\n\n", 1)[1] if raw.startswith("# Text of ") and "\n\n" in raw else raw
                parts = re.split(r"^\[page (\d+)\]$", raw, flags=re.M)
                pages = {}
                if len(parts) > 1:
                    for i in range(1, len(parts), 2):
                        pages[int(parts[i])] = parts[i + 1]
                else:
                    pages[0] = raw
                self._cache[path] = {k: (norm_text(v), loose(v)) for k, v in pages.items()}
        return self._cache[path]


def url_host(url):
    return (urllib.parse.urlsplit(url or "").hostname or "").lower()


def official_host(host, code, frame_hosts, rejected=()):
    """A host counts as official when it is a government domain, or listed as official for the jurisdiction in
    pipeline/official-sites.json, and is neither a known third-party site nor listed there as not official.
    A human records each decision with `pipeline.py hosts --add`."""
    if not host or host in NOT_OFFICIAL_HOSTS or ("www." + host) in NOT_OFFICIAL_HOSTS or strip_www(host) in rejected:
        return False
    if GOV_HOST.search(host):
        return True
    for h in frame_hosts.get(code) or []:
        h = h.lower()
        if host == h or host.endswith("." + h) or h.endswith("." + host.replace("www.", "", 1)):
            return True
    return False


def check_item(index, cid, item, record_id=None):
    """Check one evidence item. Returns (ok, kind, problems, warnings)."""
    problems, warnings = [], []
    if not isinstance(item, dict):
        return False, None, ["evidence item is not an object"], []
    path = (item.get("file") or "").strip()
    if path.endswith(".txt"):
        path = path[:-4]
    path = path[len(str(ROOT)) + 1:] if path.startswith(str(ROOT)) else path
    kind = item.get("source_kind")
    if kind not in SOURCE_KINDS:
        problems.append("source_kind %r is not one of %s" % (kind, ", ".join(SOURCE_KINDS)))
    allowed = index.files_for(cid, record_id)
    if path not in allowed:
        problems.append("file %r is not a stored source of %s" % (path, cid))
        return False, kind, problems, warnings
    if not (ROOT / path).is_file():
        problems.append("file %s is missing on disk" % path)
        return False, kind, problems, warnings
    actual = sha256_file(ROOT / path)
    if not item.get("sha256"):
        problems.append("sha256 is missing (it is in texts.json)")
    elif item["sha256"] != actual:
        problems.append("sha256 does not match %s" % path)
    quote = item.get("quote") or ""
    if not quote.strip():
        problems.append("quote is empty")
        return False, kind, problems, warnings
    if len(quote) > QUOTE_MAX:
        warnings.append("quote is %d characters (limit %d)" % (len(quote), QUOTE_MAX))
    if len(loose(quote)) < QUOTE_MIN_ALNUM:
        problems.append("quote %r is too short to identify a passage (at least %d letters or digits)" % (quote, QUOTE_MIN_ALNUM))
        return False, kind, problems, warnings
    pages = index.pages(path)
    if pages is None:
        problems.append("no text for %s; run textify" % path)
        return False, kind, problems, warnings
    nq, lq = norm_text(quote), loose(quote)
    found = [k for k, (n, l) in pages.items() if nq in n]
    how = "exact"
    if not found and len(lq) >= 20:
        found = [k for k, (n, l) in pages.items() if lq in l]
        how = "loose"
    if not found:
        problems.append("quote not found in %s: %r" % (path, quote[:80]))
        return False, kind, problems, warnings
    if how == "loose":
        warnings.append("quote matches only when spacing and punctuation are ignored")
    m = re.search(r"\bp(?:age|\.|p\.)?\s*(\d+)", item.get("locator") or "", re.I)
    if m and 0 not in pages and int(m.group(1)) not in found:
        warnings.append("quote is on page %s, not %s" % (", ".join(map(str, found[:3])), m.group(1)))
    if kind in ("official", "alt-official"):
        role, url = index.file_info(cid, record_id).get(path, (None, None))
        host = url_host(url)
        is_official = official_host(host, index.code_for(cid, record_id), index.frame_hosts, index.rejected_hosts)
        if role in SECONDARY_ROLES and is_official and kind == "official":
            warnings.append("%s was stored as the record's secondary source; from an official host it counts as "
                            "another official source (alt-official), not as the official one" % path)
            kind = "alt-official"
        elif role in SECONDARY_ROLES and not is_official:
            warnings.append("%s was stored as a secondary source, so it counts as secondary, not %s" % (path, kind))
            kind = "secondary"
        elif not is_official:
            warnings.append("host %s is not recognised as official, so this quote counts as secondary; if the host is "
                            "official, a human records it with tools/pipeline.py hosts --add" % (host or "(unknown)"))
            kind = "secondary"
    if kind == "official":
        _, url = index.file_info(cid, record_id).get(path, (None, None))
        if url and ANNOUNCEMENT_URL.search(urllib.parse.unquote(url)) and "/eli/" not in url.lower():  # ELI: a gazette
            warnings.append("%s looks like an announcement (press release, news item, fact sheet, speech): an announcement "
                            "counts at most as alt-official, even on the issuer's site, unless the page holds the "
                            "instrument's own text (AGENTS.md section 5.4)" % url)
    return not problems, kind, problems, warnings


MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9


JP_ERAS = {"令和": 2018, "平成": 1988}  # Reiwa 1 = 2019, Heisei 1 = 1989


def dates_in(text):
    """Full dates written in a quote, as ISO strings (English month names and numeric forms)."""
    t = norm_text(text)
    out = set()

    def add(y, m, d):
        try:
            out.add(dt.date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            pass
    for y, m, d in re.findall(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t):
        add(y, m, d)
    mon = "|".join(sorted(MONTHS, key=len, reverse=True))
    for d, m, y in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)?\.? (%s)\.?,? (\d{4})\b" % mon, t):
        add(y, MONTHS[m], d)
    for m, d, y in re.findall(r"\b(%s)\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})\b" % mon, t):
        add(y, MONTHS[m], d)
    for d, m, y in re.findall(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", t):
        add(y, m, d)
    for d, m, y in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)? day of (%s),? (?:in the year )?(\d{4})\b" % mon, t):
        add(y, MONTHS[m], d)  # executive orders: "this 30th day of March 2026"
    for a, b, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", t):  # day/month or month/day: accept both
        add(y, b, a)
        add(y, a, b)
    for y, m, d in re.findall(r"(\d{4})\s*[年년]\s*(\d{1,2})\s*[月월]\s*(\d{1,2})\s*[日일]", t):  # Chinese, Japanese, Korean
        add(y, m, d)
    for era, y, m, d in re.findall(r"(令和|平成)\s*(\d{1,2}|元)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", t):  # Japanese eras
        add(JP_ERAS[era] + (1 if y == "元" else int(y)), m, d)
    for y, m, d in re.findall(r"\b(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?(?!\d)", t):  # Korean 2026. 1. 20.
        add(y, m, d)
    for d, m, y in re.findall(r"ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})", t):  # Vietnamese
        add(y, m, d)
    return out


def months_in(text):
    """Year-months written in a quote without a day (April 2025, 2025年4月, 2025년 4월, tháng 4 năm 2025, 2025-04)."""
    t = norm_text(text)
    out = set()

    def add(y, m):
        if 1 <= int(m) <= 12:
            out.add("%04d-%02d" % (int(y), int(m)))
    mon = "|".join(sorted(MONTHS, key=len, reverse=True))
    for m, y in re.findall(r"(?<![\d.] )(?<!\d)\b(%s)\.?,? (\d{4})\b" % mon, t):
        add(y, MONTHS[m])
    for y, m in re.findall(r"(\d{4})\s*[年년]\s*(\d{1,2})\s*[月월](?!\s*\d{1,2}\s*[日일])", t):
        add(y, m)
    for era, y, m in re.findall(r"(令和|平成)\s*(\d{1,2}|元)\s*年\s*(\d{1,2})\s*月(?!\s*\d{1,2}\s*日)", t):
        add(JP_ERAS[era] + (1 if y == "元" else int(y)), m)
    for mt in re.finditer(r"tháng\s*(\d{1,2})\s*năm\s*(\d{4})", t):  # not when a day number precedes it
        if not re.search(r"ngày\s*\d{1,2}\s*$", t[:mt.start()]):
            add(mt.group(2), mt.group(1))
    for y, m in re.findall(r"\b(\d{4})-(\d{2})\b(?!-\d)", t):
        add(y, m)
    return out


def date_support(value, quote):
    """How one quote supports a date value: 'full', 'partial' (it shows only the year-month of a full date) or
    'unknown' (no date form the script can read)."""
    v = str(value or "")
    if not validate.FULL_DATE.match(v):
        return "full" if v and v[:4] in norm_text(quote) else "unknown"
    if v in dates_in(quote):
        return "full"
    if v[:7] in months_in(quote):
        return "partial"
    return "unknown"


def value_hint(field, value, quotes):
    """Cheap consistency checks between a value and its quotes."""
    if value in (None, "", []):
        return None
    hay = norm_text(" ".join(quotes))
    if field.startswith("date_") and re.match(r"^\d{4}", str(value)):
        year = str(value)[:4]
        y = int(year)
        eras = [("令和%s年" % ("元" if y == 2019 else y - 2018)) if y > 2018 else "",
                ("平成%s年" % ("元" if y == 1989 else y - 1988)) if 1988 < y < 2020 else ""]
        if year not in hay and str(int(year) + 543) not in hay and not any(e and e in hay.replace(" ", "") for e in eras):
            # Buddhist-era years appear in Thai sources, Japanese era years in Japanese ones
            return "warning", "no quote for %s shows the year %s" % (field, year)
        found = dates_in(" ".join(quotes))
        if found and not any(x.startswith(str(value)) for x in found):
            return "error", "the quotes for %s show %s, not %s" % (field, ", ".join(sorted(found)), value)
    if field == "official_identifier":
        nums = [n for n in re.findall(r"\d+", str(value)) if len(n) >= 2]
        if nums and not any(n in hay for n in nums):
            return "warning", "no quote for official_identifier shows its number"
    return None


def record_problems(rec, db, update=False):
    """Schema and convention checks on an extracted record (or on the fields an update changes)."""
    errors, warnings = [], []
    present = lambda k: rec.get(k) not in (None, "", [])  # noqa: E731
    if not update:
        for k in validate.REQUIRED:
            if k in SET_BY_SCRIPT or k == "verification":
                continue
            if not present(k):
                errors.append("required field %r is missing" % k)
    for k, allowed in validate.VOCAB.items():
        if present(k) and rec[k] not in allowed:
            errors.append("%s %r is not in the vocabulary" % (k, rec[k]))
    for k in ("date_published", "date_in_force", "date_last_updated"):
        v = rec.get(k)
        if v and not (validate.FULL_DATE.match(str(v)) or validate.PARTIAL_DATE.match(str(v))):
            errors.append("%s %r is not an ISO date" % (k, v))
    if "summary" in rec and rec.get("summary") is not None:
        n = len(rec["summary"])
        if n < SUMMARY_MIN or n > SUMMARY_MAX:
            errors.append("summary is %d characters (%d to %d)" % (n, SUMMARY_MIN, SUMMARY_MAX))
    if "safety_topics" in rec and rec.get("safety_topics") is not None:
        t = rec["safety_topics"]
        if not isinstance(t, list) or not (TOPICS_MIN <= len(t) <= TOPICS_MAX):
            errors.append("safety_topics needs %d to %d values" % (TOPICS_MIN, TOPICS_MAX))
        else:
            bad = [x for x in t if x not in validate.TOPICS]
            if bad:
                errors.append("topics not in the vocabulary: %s" % ", ".join(bad))
    for k in ("summary", "notes", "scope_note"):
        txt = rec.get(k) or ""
        hits = [m.group(0) for pat in PROCESS_PATTERNS for m in [re.search(pat, txt, re.I)] if m]
        if hits:
            errors.append("%s contains research-process language (%s); move it to verification.note" % (k, ", ".join(hits[:3])))
    for k in ("official_url", "secondary_url"):
        u = rec.get(k)
        if u and not re.match(r"^https?://\S+$", u):
            errors.append("%s is not an http(s) URL" % k)
    dp, di = str(rec.get("date_published") or ""), str(rec.get("date_in_force") or "")
    if validate.FULL_DATE.match(dp) and validate.FULL_DATE.match(di) and di < dp:
        warnings.append("date_in_force is before date_published")
    if rec.get("status") in IN_FORCE and "date_in_force" in rec and not rec.get("date_in_force"):
        warnings.append("status is in force but date_in_force is empty")
    if rec.get("legal_force") == "Proposed" and rec.get("status") in IN_FORCE:
        errors.append("legal_force Proposed with an in-force status")
    di_d = parse_date(rec.get("date_in_force"))
    if di_d and di_d <= dt.date.today() and rec.get("status") not in CURRENT and rec.get("status"):
        warnings.append("date_in_force %s has passed but the status is %r" % (di_d, rec["status"]))
    known_countries = {r["country"] for r in db["records"]}
    if present("country") and rec["country"] not in known_countries:
        if rec["country"] not in frame_names() and rec["country"] != "International":
            warnings.append("country %r is spelled differently from the register and the frame" % rec["country"])
    if present("official_identifier") and re.search(r"(?i)\bversion\b|^v\d|not confirmed|unknown", rec["official_identifier"]):
        warnings.append("official_identifier looks like a version label or a remark")
    if present("language") and validate.LANGUAGE_REMARK.search(validate.LANGUAGE_VARIANT.sub("", rec["language"])):
        errors.append("language %r holds a remark; give language names only and put an English translation in "
                      "english_version" % rec["language"])
    ev = rec.get("english_version")
    if ev is not None:
        if not isinstance(ev, dict) or ev.get("kind") not in validate.ENGLISH_VERSION_KINDS:
            errors.append("english_version must be {kind, url, by} with kind one of %s"
                          % ", ".join(validate.ENGLISH_VERSION_KINDS))
        elif ev["kind"] in validate.TRANSLATION_KINDS and not (ev.get("url") and ev.get("by")):
            errors.append("english_version is a translation: give its url and who made it ('by')")
    elif not update and present("language") and not validate.has_english_text(rec):
        errors.append("the official text is not in English: record english_version (none found, if none was found)")
    return errors, warnings


def evaluate(index, cid, ex, db):
    """Evidence check of one extraction. Returns a result dict with errors, warnings, level and per-field support."""
    res = {"decision": ex.get("decision"), "errors": [], "warnings": [], "fields": {}, "level": None}
    if ex.get("_error"):
        res["errors"].append(ex["_error"])
        return res
    if ex.get("decision") not in DECISIONS:
        res["errors"].append("decision %r is not one of %s" % (ex.get("decision"), ", ".join(DECISIONS)))
        return res
    if ex["decision"] not in ("record", "update"):
        return res
    rec = ex.get("record") or {}
    evidence = ex.get("evidence") or {}
    update = ex["decision"] == "update"
    target = ex.get("target_id") or (index.sources.get(cid) or {}).get("record_id")
    if update and target not in index.records:
        res["errors"].append("an update needs target_id of an existing record")
        return res
    for k in SET_BY_SCRIPT:
        if rec.get(k):
            res["warnings"].append("%s is set by the scripts; the extractor's value is ignored" % k)
    errs, warns = record_problems(rec, db, update=update)
    res["errors"] += errs
    res["warnings"] += warns
    base = dict(index.records[target]) if update else {}
    merged = dict(base, **{k: v for k, v in rec.items() if k in RECORD_FIELDS})
    ev = rec.get("english_version")
    if isinstance(ev, dict) and ev.get("kind") in validate.TRANSLATION_KINDS and ev.get("url"):
        stored = {u for _, u in index.file_info(cid, target if update else None).values() if u}
        if ev["url"] not in stored:
            res["errors"].append("english_version.url is not a stored source of %s; add it to extra_urls so the "
                                 "archiver stores it" % cid)
    if update and merged.get("english_version") is None and merged.get("language") and not validate.has_english_text(merged):
        res["warnings"].append("the official text is not in English and english_version is not recorded yet")
    confirmed = ((ex.get("judgment") or {}).get("confirmed") or []) if update else []
    fields = [k for k in FACT_FIELDS if (k in rec and rec.get(k) is not None) or k in confirmed]
    if update:
        fields += [k for k in LEVEL_FIELDS if k not in fields and merged.get(k) is not None]
    for k in fields:
        items = evidence.get(k) or []
        if isinstance(items, dict):
            items = [items]
        fr = {"items": [], "supported": False, "best_kind": None}
        kinds, level_kinds = [], []
        for it in items:
            ok, kind, probs, warns = check_item(index, cid, it, target)
            if ok and k.startswith("date_") and isinstance(it, dict) and \
                    date_support(merged.get(k), it.get("quote") or "") == "partial":
                # the quote shows only the month of a full date: it supports the field, not the level
                warns = warns + ["the quote shows only the month of %s, so it does not count for the level" % merged.get(k)]
            elif ok:
                level_kinds.append(kind)
            fr["items"].append({"ok": ok, "problems": probs, "warnings": warns})
            if ok:
                kinds.append(kind)
        fr["supported"] = bool(kinds)
        fr["best_kind"] = next((k2 for k2 in SOURCE_KINDS if k2 in level_kinds), None)
        if not items:
            msg = "%s has no evidence" % k
            (res["errors"] if (k in rec or k in LEVEL_FIELDS) else res["warnings"]).append(msg)
        elif not kinds:
            res["errors"].append("%s: no evidence item passed (%s)" % (
                k, "; ".join(p for it in fr["items"] for p in it["problems"])[:300]))
        hint = value_hint(k, merged.get(k), [it.get("quote") or "" for it in items if isinstance(it, dict)])
        if hint:
            res["errors" if hint[0] == "error" else "warnings"].append(hint[1])
        for it in fr["items"]:
            res["warnings"] += ["%s: %s" % (k, w) for w in it["warnings"]]
        res["fields"][k] = fr
    res["level"] = compute_level(res["fields"], merged)
    return res


def compute_level(fields, merged):
    need = [k for k in LEVEL_FIELDS if not (k == "date_published" and merged.get(k) is None)]
    kinds = []
    for k in need:
        fr = fields.get(k)
        kinds.append(fr["best_kind"] if fr and fr.get("supported") else None)
    if all(k == "official" for k in kinds):
        return "A"
    if all(k in ("official", "alt-official") for k in kinds):
        return "B"
    return "C"


def cmd_evidence(args):
    d, run = load_run(args.run)
    db = load_db()
    index = TextIndex(d, db)
    out = {"run_id": args.run, "generated": today(), "extractions": {}, "blind": {}}
    for sub, key in (("extractions", "extractions"), ("extractions-blind", "blind")):
        for cid, ex in agent_files(d, sub).items():
            out[key][cid] = evaluate(index, cid, ex, db)
    write_json(d / "evidence.json", out)
    bad = 0
    for cid, r in sorted(out["extractions"].items()):
        flag = "ERRORS" if r["errors"] else "ok"
        bad += 1 if r["errors"] else 0
        print("%-8s %-13s level %-4s %-6s %s" % (cid, r["decision"], r["level"] or "-", flag,
                                                 "; ".join(r["errors"][:2])[:160]))
    print("%d extraction(s), %d with errors; blind: %d. Written runs/%s/evidence.json" % (
        len(out["extractions"]), bad, len(out["blind"]), args.run))
    return 1 if bad else 0


# ----------------------------------------------------------------------------- sample and compare

def cmd_sample(args):
    d, run = load_run(args.run)
    ex = agent_files(d, "extractions")
    eligible = sorted(c for c, e in ex.items() if (e or {}).get("decision") in ("record", "update"))
    if not eligible:
        raise SystemExit("No extractions with decision record or update yet")
    n = min(len(eligible), max(args.min, math.ceil(len(eligible) * args.share)))
    rng = random.Random("blind:" + args.run)
    picked = sorted(rng.sample(eligible, n))
    sample = read_json(d / "sample.json", {}) or {}
    if sample.get("blind") and not args.force:
        print("Keeping the existing blind sample (use --force to draw again): %s" % ", ".join(sample["blind"]))
        return 0
    sample.update({"run_id": args.run, "seed": "blind:" + args.run, "blind": picked, "drawn": today()})
    write_json(d / "sample.json", sample)
    print("Blind sample: %d of %d: %s" % (n, len(eligible), ", ".join(picked)))
    print("Give these to a fresh extractor that writes into runs/%s/extractions-blind/ and does not open extractions/." % args.run)
    return 0


EXACT_FIELDS = ["date_published", "date_in_force", "date_last_updated", "status", "legal_force", "instrument_type",
                "jurisdiction_level", "region", "country"]


def same(field, a, b):
    if a in (None, "", []) and b in (None, "", []):
        return True
    if field in ("title", "original_title", "issuing_body", "short_title"):
        x, y = norm_title(a), norm_title(b)
        return difflib.SequenceMatcher(None, x, y).ratio() >= (0.9 if field != "issuing_body" else 0.75)
    if field == "official_identifier":
        return loose(a or "") == loose(b or "")
    if field in ("safety_topics", "related"):
        def ids(v):
            return {x.get("id") if isinstance(x, dict) else x for x in (v or [])}
        sa, sb = ids(a), ids(b)
        return len(sa & sb) / max(1, len(sa | sb)) >= 0.5
    return a == b


def cmd_compare(args):
    d, run = load_run(args.run)
    sample = read_json(d / "sample.json", {}) or {}
    ex, bl = agent_files(d, "extractions"), agent_files(d, "extractions-blind")
    fields = ["decision", "title", "original_title", "issuing_body", "official_identifier"] + EXACT_FIELDS + ["safety_topics"]
    stats = OrderedDict((f, [0, 0]) for f in fields)
    result = [0, 0]  # refresh runs: agreement on the resulting record (current record plus each extraction's changes)
    records = {r["id"]: r for r in load_db()["records"]}
    per, pending = {}, []
    for cid in sample.get("blind") or []:
        a, b = ex.get(cid), bl.get(cid)
        if not a or not b:
            pending.append(cid)
            continue
        base = records.get(a.get("target_id") or cid) if a.get("decision") == "update" else None
        if base and b.get("decision") == "update":
            for f in fields[1:]:
                ra = (a.get("record") or {}).get(f, base.get(f)) if f in (a.get("record") or {}) else base.get(f)
                rb = (b.get("record") or {}).get(f, base.get(f)) if f in (b.get("record") or {}) else base.get(f)
                if ra in (None, "", []) and rb in (None, "", []):
                    continue
                result[0] += 1
                result[1] += 1 if same(f, ra, rb) else 0
        diffs = []
        for f in fields:
            va = a.get("decision") if f == "decision" else (a.get("record") or {}).get(f)
            vb = b.get("decision") if f == "decision" else (b.get("record") or {}).get(f)
            if f != "decision" and va in (None, "", []) and vb in (None, "", []):
                continue
            stats[f][0] += 1
            if same(f, va, vb):
                stats[f][1] += 1
            else:
                diffs.append({"field": f, "first": va, "blind": vb})
        per[cid] = diffs
    n_all = sum(s[0] for f, s in stats.items() if f != "decision")
    a_all = sum(s[1] for f, s in stats.items() if f != "decision")
    table = OrderedDict((f, {"compared": s[0], "agree": s[1], "rate": round(s[1] / s[0], 3) if s[0] else None})
                        for f, s in stats.items())
    out = {"run_id": args.run, "generated": today(), "compared": len(per), "pending": pending,
           "overall_field_agreement": round(a_all / n_all, 3) if n_all else None, "fields": table, "disagreements": per,
           "resulting_record_agreement": round(result[1] / result[0], 3) if result[0] else None,
           "resulting_record_fields": result[0]}
    write_json(d / "agreement.json", out)
    print("Compared %d pair(s); pending: %s" % (len(per), ", ".join(pending) or "-"))
    for f, t in table.items():
        if t["compared"]:
            print("  %-20s %d/%d" % (f, t["agree"], t["compared"]))
    if out["overall_field_agreement"] is not None:
        print("Overall field agreement: %.0f%%" % (100 * out["overall_field_agreement"]))
    if out["resulting_record_agreement"] is not None:
        print("Agreement on the resulting records (refresh runs; %d field values): %.0f%%"
              % (result[0], 100 * out["resulting_record_agreement"]))
    return 0


# ----------------------------------------------------------------------------- queue

def queue(db, days, root=ROOT):
    """Records due for a refresh run, most urgent first: [(id, [reasons])]."""
    now = dt.date.today()
    reasons = defaultdict(list)
    prio = {}
    events = history.load(root)
    last_check = {}
    for e in events:
        if e.get("event") in ("changed", "re-verified", "added"):
            last_check[e["record_id"]] = max(last_check.get(e["record_id"], ""), e.get("date") or "")
    if REQUESTS.is_file():
        for line in REQUESTS.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if last_check.get(r.get("record_id"), "") < (r.get("date") or ""):
                reasons[r["record_id"]].append("requested in run %s: %s" % (r.get("run_id"), (r.get("why") or "")[:80]))
                prio[r["record_id"]] = min(prio.get(r["record_id"], 9), 0)
    for r in db["records"]:
        rid = r["id"]
        v = r.get("verification") or {}
        vd = parse_date(v.get("verified_on"))
        lc = r.get("local_copy") or {}
        add = lambda p, msg: (reasons[rid].append(msg), prio.__setitem__(rid, min(prio.get(rid, 9), p)))  # noqa: E731
        di = parse_date(r.get("date_in_force"))
        if di and di <= now and r.get("status") not in CURRENT:
            add(1, "date_in_force %s has passed but the status is %s" % (di, r.get("status")))
        if r.get("status") == "Adopted, not yet in force" and not r.get("date_in_force"):
            add(2, "adopted, not yet in force, and no in-force date")
        changed = [f for f in lc.get("files") or [] if not f.get("stale") and f.get("previous_sha256")
                   and vd and (f.get("retrieved_at") or "")[:10] > vd.isoformat()]
        if changed:
            add(3, "source changed since verification (%s)" % ", ".join(f.get("role_key") or f.get("role") for f in changed))
        if v.get("level") == "C":
            add(4, "level C")
        if lc.get("status") in ("failed", "partial", "archived-review") or lc.get("integrity_flag"):
            add(5, "local copy needs attention (%s)" % lc.get("status"))
        if not vd or (now - vd).days >= days:
            add(6, "verified %s, more than %d days ago" % (v.get("verified_on"), days))
    return sorted(((rid, rs) for rid, rs in reasons.items()), key=lambda x: (prio.get(x[0], 9), x[0]))


def cmd_queue(args):
    db = load_db()
    q = queue(db, args.days)
    if args.json:
        print(json.dumps([{"id": rid, "reasons": rs} for rid, rs in q], ensure_ascii=False, indent=1))
        return 0
    print("%d record(s) due for a refresh run:" % len(q))
    for rid, rs in q[:args.limit]:
        print("  %-10s %s" % (rid, "; ".join(rs)[:150]))
    if len(q) > args.limit:
        print("  ... and %d more (--limit)" % (len(q) - args.limit))
    return 0


# ----------------------------------------------------------------------------- assemble

def jurisdiction_code(c, rec, db):
    cell = c.get("cell") or ""
    if "/" in cell:
        return cell.split("/")[0]
    prefixes = Counter(re.sub(r"-\d+$", "", r["id"]) for r in db["records"] if r.get("jurisdiction") == rec.get("jurisdiction"))
    return prefixes.most_common(1)[0][0] if prefixes else None


def next_id(code, taken):
    nums = [int(i.rsplit("-", 1)[1]) for i in taken if re.sub(r"-\d+$", "", i) == code]
    nid = "%s-%02d" % (code, (max(nums) + 1) if nums else 1)
    taken.add(nid)
    return nid


def unique_slug(base, taken):
    s, n = base, 2
    while s in taken:
        s, n = "%s-%d" % (base, n), n + 1
    taken.add(s)
    return s


def norm_related(v, ids):
    out, bad = [], []
    for x in v or []:
        rid = x.get("id") if isinstance(x, dict) else x
        if rid in ids:
            if rid not in [o["id"] for o in out]:
                out.append({"id": rid, "slug": ids[rid]})
        elif rid:
            bad.append(rid)
    return out, bad


def short_evidence(fields_ev):
    """A compact evidence list for the history: one item per field."""
    out = []
    for k, items in fields_ev.items():
        for it in items if isinstance(items, list) else [items]:
            if isinstance(it, dict) and it.get("quote"):
                out.append({"field": k, "file": it.get("file"), "sha256": it.get("sha256"),
                            "locator": it.get("locator"), "quote": it.get("quote")})
                break
    return out


def error_field(msg):
    """The record field an evidence-script error is about, or None."""
    for f in sorted(RECORD_FIELDS, key=len, reverse=True):
        if re.search(r"(?<![a-z_])%s(?![a-z_])" % re.escape(f), msg):
            return f
    return None


def cmd_assemble(args):
    d, run = load_run(args.run)
    db = load_db()
    index = TextIndex(d, db)
    by = {r["id"]: r for r in db["records"]}
    slugs = {r["id"]: r["slug"] for r in db["records"]}
    taken_ids, taken_slugs = set(by), set(slugs.values())
    ex_all, ch_all = agent_files(d, "extractions"), agent_files(d, "checks")
    stages = run.get("stages") or {}
    new_records, updates, ctx = [], [], {}
    not_added, needs_human, unchecked, questions = [], [], [], []
    assigned = {}
    pending_related = []
    for c in candidates(d):
        if c.get("status") != "active":
            continue
        cid = c["cand_id"]
        ex = ex_all.get(cid)
        if not ex:
            unchecked.append({"cand_id": cid, "why": "no extraction"})
            continue
        dec = ex.get("decision")
        if dec in ("duplicate", "out-of-scope"):
            not_added.append({"cand_id": cid, "decision": dec, "target_id": ex.get("target_id"),
                              "title": (ex.get("record") or {}).get("title") or c.get("title_as_found"),
                              "why": (ex.get("judgment") or {}).get("scope_reasoning") or (ex.get("open_questions") or [""])[0]})
            continue
        if dec == "needs-human":
            needs_human.append({"cand_id": cid, "why": "extractor: " + ((ex.get("judgment") or {}).get("scope_reasoning") or
                                                                       "; ".join(ex.get("open_questions") or []))})
            continue
        ch = ch_all.get(cid)
        if not ch:
            unchecked.append({"cand_id": cid, "why": "not checked yet"})
            continue
        overall = ch.get("overall")
        if overall == "reject":
            not_added.append({"cand_id": cid, "decision": "rejected by the checker", "title": (ex.get("record") or {}).get("title"),
                              "why": ch.get("note")})
            continue
        rec = {k: v for k, v in (ex.get("record") or {}).items() if k in RECORD_FIELDS and k not in SET_BY_SCRIPT}
        evidence = {k: (v if isinstance(v, list) else [v]) for k, v in (ex.get("evidence") or {}).items()}
        target = ex.get("target_id") or c.get("record_id")
        is_update = dec == "update" or bool(c.get("record_id"))
        cur = by.get(target) if is_update else None
        # the values this run proposes to change; for a new record, every value is new
        proposed = {k for k, v in rec.items() if k != "verification" and (cur is None or cur.get(k) != v)}
        blockers, standing, applied = [], [], []

        def problem(field, msg, open_question=False):
            # A problem with a value the run changes, or with a new record, holds the record back. A problem with a
            # value the run leaves as published (an old claim, a source that cannot be stored) becomes an open
            # question and does not hold back the run's checked corrections; so does a possible newer version,
            # also for a new record, which is right as recorded until the newer one is stored.
            if open_question:
                standing.append(msg)
            else:
                (blockers if cur is None or (field is not None and field in proposed) else standing).append(msg)
        if overall not in ("accept", "accept-with-fixes"):
            problem(None, "checker: %s" % (ch.get("note") or overall))
        for field, fv in (ch.get("fields") or {}).items():
            verdict = (fv or {}).get("verdict")
            fix = (fv or {}).get("fix")
            if verdict in ("contradicted", "unsupported"):
                if fix and isinstance(fix, dict) and fix.get("evidence"):
                    oks = [check_item(index, cid, it, target)[0] for it in fix["evidence"]]
                    if all(oks):
                        rec[field] = fix.get("value")
                        evidence[field] = fix["evidence"]
                        applied.append(field)
                        continue
                    problem(field, "the checker's fix for %s did not pass the evidence check" % field)
                else:
                    problem(field, "%s is %s and the checker gave no evidence-backed fix" % (field, verdict))
        for claim in ch.get("summary_claims") or []:
            # a claim of the old summary no longer blocks once the checker's evidence-backed summary fix replaced it
            if claim.get("verdict") in ("unsupported", "contradicted") and "summary" not in applied:
                problem("summary", "summary claim %s: %r" % (claim["verdict"], (claim.get("claim") or "")[:80]))
        # something newer counts unless it already has its own record ("already recorded as CN-17")
        newer = [x for x in (ch.get("newer_versions") or []) + (ch.get("extra_urls") or [])
                 if not any(t in by and t != target for t in re.findall(r"\b[A-Z0-9]{2,6}(?:-[A-Z]{2})?-\d{2}\b", str(x)))]
        if newer:
            problem(None, "the checker found something possibly newer: %s" % "; ".join(str(x) for x in newer)[:300],
                    open_question=True)
        # a check counts only when it covers every factual field the record sets or confirms
        need = [k for k in FACT_FIELDS if (ex.get("record") or {}).get(k) is not None]
        if is_update:
            need += [k for k in ((ex.get("judgment") or {}).get("confirmed") or []) if k in FACT_FIELDS]
            need += [k for k in LEVEL_FIELDS if (by.get(target) or {}).get(k) is not None]
        verdicts = ch.get("fields") or {}
        missing = [k for k in dict.fromkeys(need) if (verdicts.get(k) or {}).get("verdict") not in VERDICTS]
        for k in missing:
            problem(k, "the checker gave no verdict for %s" % k)
        scope = ch.get("scope") or {}
        if scope.get("assessment") == "out":
            problem(None, "the checker judges it out of scope: %s" % (scope.get("note") or "no reason given"))
        elif scope.get("assessment") == "borderline" and scope.get("note") and not rec.get("scope_note"):
            rec["scope_note"] = scope["note"]  # the checker flags a borderline case the extractor did not
            applied.append("scope_note")
        new_summary = (ex.get("record") or {}).get("summary") is not None
        if new_summary and not [x for x in ch.get("summary_claims") or [] if x.get("verdict") in VERDICTS]:
            problem("summary", "the checker checked no claim of the summary")
        ev = evaluate(index, cid, dict(ex, record=rec, evidence=evidence), db)
        for e in ev["errors"]:
            problem(error_field(e), e)
        if blockers:
            needs_human.append({"cand_id": cid, "record_id": target if is_update else None,
                                "why": "; ".join(blockers + standing)[:800]})
            continue
        if standing:
            questions.append({"cand_id": cid, "record_id": target, "why": "; ".join(standing)[:800]})
        level = ev["level"]
        v_in = (ex.get("record") or {}).get("verification") or {}
        note = (v_in.get("note") or "").strip()
        if not note and target in by and dec == "update":  # a re-verification keeps the record's own note ...
            note = ((by[target].get("verification") or {}).get("note") or "").strip()
            if level != "C" and "CAUTION" in note:  # ... unless it warns about a level the evidence no longer has
                note = ""
        if level == "C" and "CAUTION" not in note:
            note = ("CAUTION: no official source confirms the title, date and status; the record rests on secondary sources. "
                    + note).strip()
        checked = "%s (%s), %s" % (ch.get("tool") or (stages.get("check") or {}).get("tool"),
                                    ch.get("model") or (stages.get("check") or {}).get("model"), ch.get("checked_on") or today())
        n_sup = len([1 for fv in (ch.get("fields") or {}).values() if (fv or {}).get("verdict") == "supported"])
        verification = {"level": level, "verified_on": today(), "method": METHOD_TOKENS[level],
                        "note": note or "Pipeline run %s; evidence in runs/%s/extractions/%s.json." % (args.run, args.run, cid),
                        "second_check": "Independent check by %s: %d field(s) supported%s." % (
                            checked, n_sup, (", fixes applied to " + ", ".join(applied)) if applied else "")}
        fields_ctx = {}
        if dec == "update" or (c.get("record_id") and dec == "record"):
            if target not in by:
                needs_human.append({"cand_id": cid, "why": "update target %r does not exist" % target})
                continue
            cur = by[target]
            changes = {k: v for k, v in rec.items() if k != "verification" and cur.get(k) != v}
            if "related" in changes:
                changes["related"], bad = norm_related(changes["related"], slugs)
                if changes["related"] == cur.get("related"):
                    changes.pop("related")
            reasons = (ex.get("judgment") or {}).get("changes") or {}
            for k in changes:
                fields_ctx[k] = {"reason": reasons.get(k) if isinstance(reasons, dict) else None,
                                 "evidence": short_evidence({k: evidence.get(k) or []})}
            if cur.get("verification", {}).get("level") != level:
                fields_ctx["verification.level"] = {"reason": "level computed from the evidence by tools/pipeline.py",
                                                    "evidence": []}
            upd = dict(changes, id=target, verification=verification)
            updates.append(upd)
            confirmed = (ex.get("judgment") or {}).get("confirmed") or []
            ctx[target] = {"reason": "pipeline run %s (%s), candidate %s" % (args.run, run["type"], cid), "fields": fields_ctx,
                           "confirmed": confirmed, "evidence": short_evidence({k: evidence.get(k) or [] for k in confirmed}),
                           "cand_id": cid}
            assigned[cid] = target
            continue
        code = jurisdiction_code(c, rec, db)
        if not code:
            needs_human.append({"cand_id": cid, "why": "no jurisdiction code (the candidate has no frame cell)"})
            continue
        nid = next_id(code, taken_ids)
        if not validate.ID_FORMAT.match(nid):
            needs_human.append({"cand_id": cid, "why": "the next ID %s does not fit the ID format" % nid})
            continue
        slug = unique_slug(slugify(rec.get("short_title") or rec.get("title")), taken_slugs)
        slugs[nid] = slug
        full = OrderedDict((k, rec.get(k)) for k in RECORD_FIELDS)
        full.update({"id": nid, "slug": slug, "verification": verification})
        full["safety_topics"] = full.get("safety_topics") or []
        # related may name existing records or candidates of this run (C012); the checker can add missing links
        pending_related.append((full, list(rec.get("related") or []) + list(ch.get("related_missing") or [])))
        lc = ((index.sources.get(cid) or {}).get("main"))
        if lc and lc.get("files"):
            full["local_copy"] = lc
        new_records.append(full)
        ctx[nid] = {"reason": "found in pipeline run %s, candidate %s (%s)" % (args.run, cid, c.get("cell") or "-"),
                    "evidence": short_evidence(evidence), "cand_id": cid}
        assigned[cid] = nid
    # related links: resolve now that new IDs exist; make every link two-way
    rev = defaultdict(list)
    for full, wanted in pending_related:
        wanted = [assigned.get(x.get("id") if isinstance(x, dict) else x, x.get("id") if isinstance(x, dict) else x)
                  for x in wanted or []]  # candidate IDs of this run become the IDs their records were given
        full["related"], bad = norm_related(wanted, slugs)
        if bad:
            print("WARNING  %s: related IDs that do not exist were dropped: %s" % (full["id"], ", ".join(bad)))
        for x in full["related"]:
            rev[x["id"]].append(full["id"])
    new_by = {r["id"]: r for r in new_records}
    upd_by = {u["id"]: u for u in updates}
    for tid, sources_ in rev.items():
        if tid in new_by:
            have = {x["id"] for x in new_by[tid]["related"]}
            for s in sources_:
                if s not in have:
                    new_by[tid]["related"].append({"id": s, "slug": slugs[s]})
            continue
        cur_rel = list((upd_by.get(tid) or {}).get("related") or by[tid].get("related") or [])
        have = {x.get("id") for x in cur_rel}
        add = [s for s in sources_ if s not in have]
        if not add:
            continue
        cur_rel += [{"id": s, "slug": slugs[s]} for s in add]
        if tid in upd_by:
            upd_by[tid]["related"] = cur_rel
        else:
            upd_by[tid] = {"id": tid, "related": cur_rel}
            updates.append(upd_by[tid])
        ctx.setdefault(tid, {}).setdefault("fields", {})["related"] = {
            "reason": "two-way link to %s added in run %s" % (", ".join(add), args.run), "evidence": []}
    for q in questions:  # a new record's question names the ID it was given
        if not q.get("record_id") and q.get("cand_id") in assigned:
            q["record_id"] = assigned[q["cand_id"]]
    ex_stage = stages.get("extract") or {}
    prov = {"date": today(), "agent": ex_stage.get("tool") or (run.get("coordinator") or {}).get("tool"),
            "model": ex_stage.get("model") or (run.get("coordinator") or {}).get("model"),
            "scope": "pipeline run %s (%s: %s)" % (args.run, run["type"], run.get("scope") or "queue"),
            "run_id": args.run, "stages": stages}
    out = {"provenance": prov, "records": new_records, "updates": updates, "history_context": ctx,
           "assigned": assigned, "not_added": not_added, "needs_human": needs_human, "questions": questions,
           "unchecked": unchecked,
           "summary": "%d new, %d update(s), %d not added, %d need a human, %d merged with an open question, %d not ready" % (
               len(new_records), len(updates), len(not_added), len(needs_human), len(questions), len(unchecked))}
    write_json(d / "pass.json", out)
    run["status"] = "assembled"
    save_run(d, run)
    print(out["summary"])
    for x in needs_human:
        print("  needs-human %-6s %s" % (x["cand_id"], x["why"][:140]))
    for x in questions:
        print("  question    %-6s %s" % (x["cand_id"], x["why"][:140]))
    for x in unchecked:
        print("  not ready   %-6s %s" % (x["cand_id"], x["why"]))
    print("Next: python3 tools/merge.py runs/%s/pass.json --dry-run" % args.run)
    return 0


# ----------------------------------------------------------------------------- report

def cmd_report(args):
    d, run = load_run(args.run)
    db = load_db()
    by = {r["id"]: r for r in db["records"]}
    p = read_json(d / "pass.json", {}) or {}
    events = [e for e in history.load() if e.get("run_id") == args.run]
    merged = bool(events)
    agr = read_json(d / "agreement.json", {}) or {}
    cands = candidates(d)
    logs = read_log(d)
    ex = agent_files(d, "extractions")
    sample = read_json(d / "sample.json", {}) or {}
    st = run.get("stages") or {}
    added = [e for e in events if e["event"] == "added"]
    changed = [e for e in events if e["event"] == "changed"]
    rever = [e for e in events if e["event"] == "re-verified"]
    accepted = sorted(set((p.get("assigned") or {}).values()) & {e["record_id"] for e in added + changed + rever})
    if accepted and not sample.get("human"):
        rng = random.Random("human:" + args.run)
        sample["human"] = sorted(rng.sample(accepted, min(5, len(accepted))))
        write_json(d / "sample.json", sample)
    L = ["# Run %s" % args.run, "",
         "<!-- coordinator: one paragraph here on what a human should look at first -->", "",
         "Type: %s. Scope: %s. Started %s; report written %s.%s" % (
             run["type"], run.get("scope") or "refresh queue", run["started"], today(),
             "" if merged else " **Not merged yet**: the lists below come from pass.json."), "",
         "| Stage | Tool | Model | Date |", "|---|---|---|---|"]
    for s in STAGES:
        x = st.get(s) or {}
        L.append("| %s | %s | %s | %s |" % (s, x.get("tool") or "-", x.get("model") or "-", x.get("date") or "-"))
    sc = Counter(c.get("status") for c in cands)
    L += ["", "## Summary", "",
          "- Candidates: %d (%s)" % (len(cands), ", ".join("%s %d" % kv for kv in sc.most_common())),
          "- Added: %d; fields changed: %d in %d record(s); re-verified without change: %d" % (
              len(added) if merged else len(p.get("records") or []), len(changed), len({e["record_id"] for e in changed}),
              len(rever)),
          "- Not added: %d; need a human: %d; not ready: %d" % (
              len(p.get("not_added") or []), len(p.get("needs_human") or []), len(p.get("unchecked") or []))]
    if agr.get("overall_field_agreement") is not None:
        L.append("- Repeatability: %.0f%% field agreement between blind double extractions (%d pair(s))" % (
            100 * agr["overall_field_agreement"], agr.get("compared") or 0)
            + ("; %.0f%% agreement on the resulting records (%d field values; in a refresh run the first figure counts "
               "only fields that an extraction changed)" % (100 * agr["resulting_record_agreement"],
                                                            agr.get("resulting_record_fields") or 0)
               if agr.get("resulting_record_agreement") is not None else ""))
    L += ["", "## Added", ""]
    rows = added if merged else [{"record_id": r["id"], "new": "%s; %s; level %s" % (
        r.get("short_title"), r.get("status"), r["verification"]["level"])} for r in p.get("records") or []]
    L += ["- **%s** %s" % (e["record_id"], e.get("new") or "") for e in rows] or ["None."]
    L += ["", "## Changed", ""]
    L += ["- **%s** %s%s" % (e["record_id"], history.describe(e), (" (%s)" % e["reason"]) if e.get("reason") else "")
          for e in changed] or ["None."]
    L += ["", "## Re-verified without change", ""]
    L += [", ".join(e["record_id"] for e in rever) or "None."]
    L += ["", "## Needs a human", "", "Held back: a value this run changes is not settled. The published record stays as it was."
          if p.get("needs_human") else "", ""]
    L += ["- %s: %s" % (x["cand_id"], x["why"]) for x in p.get("needs_human") or []] or ["None."]
    L += ["", "## Merged with an open question", "", "The run's checked corrections are merged; these points about values "
          "it left as published are open questions (GitHub issues, `pipeline.py questions --sync`)." if p.get("questions")
          else "", ""]
    L += ["- %s: %s" % (x["cand_id"], x["why"]) for x in p.get("questions") or []] or ["None."]
    L += ["", "## Not added", ""]
    L += ["- %s %s: %s%s" % (x["cand_id"], x.get("title") or "", x.get("decision"),
                             (" (%s)" % x["why"]) if x.get("why") else "") for x in p.get("not_added") or []] or ["None."]
    dropped = [c for c in cands if c.get("status") in ("in-register", "duplicate-in-run", "out-of-scope", "refresh-request")]
    if dropped:
        L += ["", "Dropped before extraction:", ""]
        L += ["- %s (%s): %s" % (c.get("title_as_found"), c.get("cell") or "-", c["status"] +
                                 (" " + (c.get("record_id") or c.get("duplicate_of") or "") if c.get("record_id") or c.get("duplicate_of") else ""))
              for c in dropped]
    if agr.get("fields"):
        L += ["", "## Repeatability", "", "Blind second extraction of %d candidate(s) (AGENTS.md section 7.4)." % agr.get("compared", 0), "",
              "| Field | Compared | Agree |", "|---|---:|---:|"]
        for f, t in agr["fields"].items():
            if t["compared"]:
                L.append("| %s | %d | %d |" % (f, t["compared"], t["agree"]))
    L += ["", "## Human sample", ""]
    if sample.get("human"):
        L += ["Check these records against their stored sources, then log the result, for example:", "",
              "    python3 tools/pipeline.py log-human --run %s --id %s --result ok --note \"...\"" % (args.run, sample["human"][0]), ""]
        L += ["- [ ] %s %s" % (rid, (by.get(rid) or {}).get("short_title") or "") for rid in sample["human"]]
    else:
        L.append("Drawn after the merge.")
    humans = [e for e in events if e["event"] in ("human-checked", "scope-decision")]
    if humans:
        L += ["", "Logged:", ""] + ["- %s %s (%s)" % (e["record_id"], history.describe(e), e.get("model") or "human")
                                    for e in humans]
    if run["type"] == "discover":
        oc = Counter(l.get("outcome") for l in logs)
        L += ["", "## Search coverage", "",
              "%d of %d cells logged (%s)." % (len({l.get('cell') for l in logs}), len(run.get("cells") or []),
                                                ", ".join("%s %d" % kv for kv in oc.most_common()))]
        blocked = [l for l in logs if l.get("outcome") == "blocked"]
        L += ["- blocked: %s: %s" % (l.get("cell"), (l.get("note") or "")[:120]) for l in blocked]
        missing = (read_json(d / "candidates.json", {}) or {}).get("cells_without_log") or []
        if missing:
            L.append("- not searched: %s" % ", ".join(missing))
    review = defaultdict(set)
    for cid, res in ((read_json(d / "evidence.json", {}) or {}).get("extractions") or {}).items():
        for w in res.get("warnings") or []:
            m = re.search(r"host (\S+) is not recognised as official", w)
            if m and m.group(1) != "(unknown)":
                review[strip_www(m.group(1))].add(cid)
    if review:
        L += ["", "## Hosts to review", "",
              "Quotes from these hosts counted as secondary because the host is neither a government domain nor listed in "
              "`pipeline/official-sites.json`. If the issuing body runs the host, or uses it as its own channel, record it "
              "with `python3 tools/pipeline.py hosts --add HOST --code CODE --status official --by NAME --operator ... "
              "--evidence-url ...`, and run `evidence` again.", ""]
        L += ["- %s: %s" % (h, ", ".join(sorted(c))) for h, c in sorted(review.items())]
    leads = [(cid, x) for cid, e in ex.items() for x in (e or {}).get("leads") or []]
    oq = [(cid, x) for cid, e in ex.items() for x in (e or {}).get("open_questions") or []]
    if leads or oq:
        L += ["", "## Leads and open questions", ""]
        L += ["- lead from %s: %s" % (cid, x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)) for cid, x in leads]
        L += ["- %s: %s" % (cid, x) for cid, x in oq]
    text = "\n".join(L) + "\n"
    old = (d / "report.md").read_text(encoding="utf-8") if (d / "report.md").is_file() else ""
    m = re.search(r"<!-- coordinator: .*?-->\n(.*?)\n\nType:", old, re.S)
    if m and m.group(1).strip():
        text = text.replace("<!-- coordinator: one paragraph here on what a human should look at first -->",
                            "<!-- coordinator: one paragraph here on what a human should look at first -->\n" + m.group(1).strip())
    (d / "report.md").write_text(text, encoding="utf-8")
    if merged:
        run["status"] = "merged"
        save_run(d, run)
        build.write_history_md()  # HISTORY.md links each run to its report, which exists only from now on
    print("Written runs/%s/report.md (%s)" % (args.run, "merged" if merged else "before merge"))
    return 0


# ----------------------------------------------------------------------------- human and scope events

def cmd_log_human(args):
    db = load_db()
    if args.id not in {r["id"] for r in db["records"]}:
        raise SystemExit("No record %s" % args.id)
    if args.result not in ("ok", "problem"):
        raise SystemExit("--result is ok or problem")
    history.append([history.event(args.id, "human-checked", run_id=args.run, new="%s: %s" % (args.result, args.note or ""),
                                  tool="human", model=args.by)])
    build.write_js(build.normalise(db))
    build.write_history_md()
    print("Logged a human check of %s (%s)." % (args.id, args.result))
    if args.result == "problem":
        print("Fix it with a refresh run: python3 tools/pipeline.py new --type refresh --scope ids:%s" % args.id)
    return 0


def cmd_log_scope(args):
    db = load_db()
    rec = {r["id"]: r for r in db["records"]}.get(args.id)
    if not rec:
        raise SystemExit("No record %s" % args.id)
    history.append([history.event(args.id, "scope-decision", run_id=args.run, new="%s: %s" % (args.decision, args.note),
                                  tool="human", model=args.by)])
    line = "- **%s** (%s): %s. %s *%s, %s.*\n" % (rec.get("short_title") or rec["title"], args.id, args.decision,
                                                   args.note.rstrip(".") + ".", args.by or "Maintainer", today())
    with open(SCOPE_DECISIONS, "a", encoding="utf-8") as f:
        f.write(line)
    build.write_js(build.normalise(db))
    build.write_history_md()
    print("Logged the scope decision and added it to pipeline/scope-decisions.md.")
    if args.decision == "out":
        print("Records are never deleted: give the record a status and a note in a refresh run, or keep it with a scope note.")
    return 0


# ----------------------------------------------------------------------------- official sites

HOST_REVIEW = ROOT / "pipeline" / "host-review.json"


def pending_site(e):
    return e.get("status") == "proposed" or e.get("decided_by") == "seed"


def cmd_hosts(args):
    data = load_sites()
    sites = data.setdefault("sites", [])
    if getattr(args, "confirm_gov", False):
        # a seed on a government domain counts as official by the domain rule anyway; a maintainer confirms them at once
        if not args.by:
            raise SystemExit("--confirm-gov needs --by (the maintainer who decides)")
        n = 0
        for e in sites:
            if e.get("decided_by") == "seed" and e.get("status") == "official" and GOV_HOST.search(strip_www(e["host"]).lower()):
                e["previous"] = {k: e.get(k) for k in ("status", "decided_by", "decided_on", "note")}
                e.update(decided_by=args.by, decided_on=today(),
                         note="A government domain, which the evidence script counts as official by the domain rule "
                              "(AGENTS.md section 7.6); confirmed in bulk with the other seeds on government domains.")
                n += 1
        write_json(SITES, data)
        print("Confirmed %d seed host(s) on government domains as official (decided by %s)." % (n, args.by))
        return 0
    if getattr(args, "batches", None):
        # the host reviewers' findings (pipeline/roles/hosts.md) grouped into batch questions for maintainers
        d = RUNS / args.batches
        found = {}
        for f in sorted((d / "hosts").glob("*.json")):
            for h in (read_json(f, {}) or {}).get("hosts") or []:
                found[(h.get("code"), strip_www(h.get("host") or ""))] = h
        own = {q.get("subject") for q in (read_json(QUESTIONS, {}) or {}).get("questions") or []
               if q.get("kind") == "host" and q.get("state") == "open"}
        todo = [e for e in sites if pending_site(e) and strip_www(e["host"]) not in own]
        rows = []
        for e in sorted(todo, key=lambda e: (e["code"], e["host"])):
            h = found.get((e["code"], strip_www(e["host"]))) or {}
            rows.append({"code": e["code"], "host": strip_www(e["host"]), "operator": h.get("operator"),
                         "url": h.get("url"), "quote": h.get("quote"), "suggestion": h.get("suggestion"),
                         "note": h.get("note")})
        size = args.size or 15
        batches = [{"id": "%s-%d" % (args.batches, i + 1), "hosts": rows[i * size:(i + 1) * size]}
                   for i in range((len(rows) + size - 1) // size)]
        write_json(HOST_REVIEW, {"about": "Pending hosts of pipeline/official-sites.json in batches for maintainers' "
                                          "decisions (AGENTS.md section 7.6), with what the host reviewers of run %s "
                                          "found about who runs each. Written by tools/pipeline.py hosts --batches; "
                                          "`questions --sync` opens one issue per batch." % args.batches,
                                 "run_id": args.batches, "batches": batches})
        print("%d pending host(s) in %d batch(es) in pipeline/host-review.json; %d without a finding." % (
            len(rows), len(batches), sum(1 for r in rows if not r.get("operator"))))
        return 0
    if args.add:
        host = strip_www(args.add)
        if not (args.code and args.status and args.by):
            raise SystemExit("--add needs --code, --status and --by")
        if args.status not in SITE_STATUSES:
            raise SystemExit("--status must be one of %s" % ", ".join(SITE_STATUSES))
        codes = {j["code"] for j in load_frame().get("jurisdictions") or []}
        if args.code not in codes:
            raise SystemExit("%s is not a jurisdiction in pipeline/frame.json" % args.code)
        if args.status != "proposed" and not (args.evidence_url or args.note):
            raise SystemExit("a decision needs --evidence-url (the page that shows who runs the host) or --note")
        entry = OrderedDict([("code", args.code), ("host", host), ("status", args.status), ("operator", args.operator),
                             ("kind", args.kind),
                             ("evidence", {"url": args.evidence_url, "quote": args.quote, "checked_on": today()}
                              if args.evidence_url else None),
                             ("decided_by", args.by), ("decided_on", today()), ("note", args.note)])
        old = next((e for e in sites if e.get("code") == args.code and strip_www(e.get("host")) == host), None)
        if old:
            entry["previous"] = {k: old.get(k) for k in ("status", "decided_by", "decided_on", "note")}
            sites[sites.index(old)] = entry
        else:
            sites.append(entry)
        sites.sort(key=lambda e: (e["code"], e["host"]))
        write_json(SITES, data)
        print("%s %s: %s (%s)%s" % (args.code, host, args.status, args.by, ", replacing %s" % old["status"] if old else ""))
        return 0
    if args.code or args.pending:
        rows = [e for e in sites if (not args.code or e["code"] == args.code)
                and (not args.pending or e["status"] == "proposed" or e.get("decided_by") == "seed")]
        for e in rows:
            print("%-7s %-40s %-13s %-10s %s" % (e["code"], e["host"], e["status"], e.get("decided_by") or "-",
                                                (e.get("operator") or e.get("note") or "")[:70]))
        print("%d entr%s" % (len(rows), "y" if len(rows) == 1 else "ies"))
        return 0
    st = Counter(e["status"] for e in sites)
    seeds = sum(1 for e in sites if e.get("decided_by") == "seed")
    print("pipeline/official-sites.json: %d sites; %s." % (len(sites), ", ".join("%s %d" % kv for kv in st.most_common())))
    print("%d official entries are seeds from records' official_url, not yet reviewed by a person; %d proposed entries "
          "wait for a decision. List them with --pending." % (seeds, st.get("proposed", 0)))
    return 0


# ----------------------------------------------------------------------------- questions for humans

QUESTIONS = ROOT / "pipeline" / "questions.json"
DECIDERS = {"OWNER", "MEMBER", "COLLABORATOR"}
ID_TOKEN = re.compile(r"\b[A-Z0-9]{2,6}(?:-[A-Z]{2})?-\d{2}\b")
HOST_WARNING = re.compile(r"host (\S+) is not recognised as official")


def github_repo():
    """owner/name of the GitHub repository, from questions.json or the origin remote."""
    q = read_json(QUESTIONS, {}) or {}
    if q.get("repo"):
        return q["repo"]
    url = subprocess.run(["git", "-C", str(ROOT), "config", "--get", "remote.origin.url"], capture_output=True,
                         text=True).stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
    if not m:
        raise SystemExit("Cannot tell the GitHub repository; set \"repo\" in pipeline/questions.json")
    return m.group(1)


AGENT_MARK = "<!-- every-ai-policy-ever:agent -->"
_CAN_WRITE = {}


def can_write(repo):
    """Whether the signed-in GitHub account may write to repo. Only maintainers' runs post questions, apply decisions
    and answer suggestions; a contributor's run in a fork leaves that to the maintainers after the merge."""
    if os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_REPOSITORY") == repo:
        return True  # a workflow of this repository, with the permissions its workflow file grants
    if repo not in _CAN_WRITE:
        res = subprocess.run(["gh", "api", "repos/%s" % repo, "--jq", ".permissions.push"], capture_output=True,
                             text=True) if shutil.which("gh") else None
        _CAN_WRITE[repo] = bool(res and res.returncode == 0 and res.stdout.strip() == "true")
    return _CAN_WRITE[repo]


def not_a_maintainer(repo, what):
    print("Skipped %s: your GitHub account has no write access to %s, so nothing is read from or posted to its issues. "
          "That is normal for a contributor: open a pull request with your run, and the maintainers' next run posts its "
          "questions and applies decisions." % (what, repo))
    return 0


def gh(*args, input_text=None):
    if not shutil.which("gh"):
        raise SystemExit("The GitHub CLI (gh) is needed for questions --sync and --apply")
    args = list(args)
    if args[:1] == ["issue"] and args[1:2] and args[1] in ("create", "comment", "close"):
        # everything the pipeline posts carries the agent marker, so that it is never read as a maintainer's decision
        for flag in ("--body", "--comment"):
            if flag in args:
                args[args.index(flag) + 1] += "\n\n" + AGENT_MARK
        if "--body-file" in args and input_text is not None:
            input_text += "\n\n" + AGENT_MARK
    res = subprocess.run(["gh"] + args, capture_output=True, text=True, input=input_text)
    if res.returncode:
        raise SystemExit("gh %s failed: %s" % (" ".join(args[:2]), res.stderr.strip()[:300]))
    return res.stdout


def run_order():
    """Run IDs in the order their events entered the history; runs without events after them, by start date."""
    order = []
    for e in history.load():
        if e.get("run_id") and e["run_id"] not in order:
            order.append(e["run_id"])
    rest = sorted((read_json(p / "run.json", {}) or {}).get("started", "") + " " + p.name
                  for p in RUNS.iterdir() if (p / "run.json").is_file() and p.name not in order) if RUNS.is_dir() else []
    return [r for r in order if (RUNS / r / "run.json").is_file()] + [x.split(" ", 1)[1] for x in rest]


def collect_questions(db):
    """Every open question the pipeline's files imply, keyed: record questions from the runs' pass.json (the latest
    run that touched a record decides), hosts waiting for a decision, and human samples not yet logged."""
    by = {r["id"]: r for r in db["records"]}
    events = history.load()
    out = OrderedDict()
    state = {}  # record ID -> open question from the latest run that raised one, or None once a later run settled it
    for run_id in run_order():
        p = read_json(RUNS / run_id / "pass.json", {}) or {}
        # a record counts as checked again only when the run changed or re-verified it, not when it only gained links
        touched = {u.get("id") for u in p.get("updates") or [] if set(u) - {"id", "related"}} | \
                  {r.get("id") for r in p.get("records") or []}
        raised = {}
        for x, held in [(x, True) for x in p.get("needs_human") or []] + [(x, False) for x in p.get("questions") or []]:
            rid = x.get("record_id") or (x.get("cand_id") if x.get("cand_id") in by else None)
            key = "record:%s@%s" % (rid, run_id) if rid else "candidate:%s@%s" % (x.get("cand_id"), run_id)
            title = None
            if not rid:  # a candidate has no record yet: name it from its extraction or the collector's candidate
                ex = read_json(RUNS / run_id / "extractions" / ("%s.json" % x.get("cand_id")), {}) or {}
                cand = next((c for c in (read_json(RUNS / run_id / "candidates.json", {}) or {}).get("candidates") or []
                             if c.get("cand_id") == x.get("cand_id")), {})
                title = (ex.get("record") or {}).get("title") or cand.get("title_as_found")
            raised[rid or key] = {"key": key, "kind": "record" if rid else "candidate", "subject": rid or x.get("cand_id"),
                                  "run_id": run_id, "held_back": held, "why": x.get("why"), "records": [rid] if rid else [],
                                  "title": title}
        for rid in touched:
            if rid not in raised:
                state[rid] = None  # a later run checked the record without raising anything
        state.update(raised)
    decided = {(e["record_id"], e.get("run_id")) for e in events if e.get("event") == "human-decision"}
    for subj, q in state.items():
        if q and (q["subject"], q["key"]) not in decided:
            out[q["key"]] = q
    sites = load_sites()
    known = {strip_www(e["host"]) for e in sites.get("sites") or []}
    for e in sites.get("sites") or []:
        if e["status"] == "proposed":
            out["host:%s" % strip_www(e["host"])] = {"key": "host:%s" % strip_www(e["host"]), "kind": "host",
                                                     "subject": strip_www(e["host"]), "code": e["code"],
                                                     "why": e.get("note"), "operator": e.get("operator"),
                                                     "evidence": e.get("evidence"), "records": []}
    pending = {strip_www(e["host"]) for e in sites.get("sites") or [] if pending_site(e)}
    for b in (read_json(HOST_REVIEW, {}) or {}).get("batches") or []:
        left = [h for h in b.get("hosts") or [] if h.get("host") in pending]
        if left:
            out["hosts:%s" % b["id"]] = {"key": "hosts:%s" % b["id"], "kind": "hosts", "subject": b["id"], "hosts": left,
                                        "records": [], "why": "Hosts in pipeline/official-sites.json that no person has "
                                                              "reviewed yet (seeds from records' official_url)."}
    for run_id in run_order():
        cells = {c.get("cand_id"): c.get("cell") for c in
                 (read_json(RUNS / run_id / "candidates.json", {}) or {}).get("candidates") or [] if c.get("cand_id")}
        assigned = (read_json(RUNS / run_id / "pass.json", {}) or {}).get("assigned") or {}
        for cid, res in ((read_json(RUNS / run_id / "evidence.json", {}) or {}).get("extractions") or {}).items():
            for w in res.get("warnings") or []:
                m = HOST_WARNING.search(w)
                h = strip_www(m.group(1)) if m else None
                if not h or h == "(unknown)" or h in known:
                    continue
                code = (cells.get(cid) or "").split("/")[0] or re.sub(r"-\d+$", "", cid)
                cid = assigned.get(cid) or cid  # a discover run's candidate is named by the record it became
                q = out.setdefault("host:%s" % h, {"key": "host:%s" % h, "kind": "host", "subject": h,
                                                   "code": code, "records": [],
                                                   "why": "Quotes from this host counted as secondary because it is "
                                                          "neither a government domain nor in pipeline/official-sites.json."})
                if cid not in q["records"]:
                    q["records"].append(cid)
    logged = {(e.get("run_id"), e["record_id"]) for e in events if e.get("event") == "human-checked"}
    for run_id in run_order():
        todo = [rid for rid in (read_json(RUNS / run_id / "sample.json", {}) or {}).get("human") or []
                if (run_id, rid) not in logged and rid in by]
        if todo:
            out["sample:%s" % run_id] = {"key": "sample:%s" % run_id, "kind": "sample", "subject": run_id,
                                         "run_id": run_id, "records": todo,
                                         "why": "Human sample of run %s: check each record against its stored sources." % run_id}
    return out


def question_title(q, by):
    if q["kind"] == "candidate":
        return "Candidate %s, %s: not added, open question from run %s" % (q["subject"], (q.get("title") or "")[:90], q["run_id"])
    if q["kind"] == "record":
        r = by.get(q["subject"]) or {}
        return "%s %s: open question from run %s" % (q["subject"], r.get("short_title") or r.get("title") or "", q["run_id"])
    if q["kind"] == "host":
        return "Is %s an official site for %s?" % (q["subject"], q.get("code"))
    if q["kind"] == "hosts":
        return "Which of these %d sites are official? (host review %s)" % (len(q.get("hosts") or []), q["subject"])
    return "Human sample of run %s (%d records)" % (q["subject"], len(q["records"]))


def question_body(q, by, repo):
    blob = "https://github.com/%s/blob/main/" % repo
    L = []
    if q["kind"] in ("record", "candidate"):
        r = by.get(q["subject"]) or {}
        run = q["run_id"]
        L += [("**Record:** %s, %s" % (q["subject"], r.get("title") or "")) if q["kind"] == "record" else
              ("**Candidate:** %s, %s (not in the register)" % (q["subject"], q.get("title") or "")),
              "**Run:** [%s](%sruns/%s/report.md)" % (run, blob, run),
              "**Now:** " + ("the run's change is held back; the published record is unchanged." if q.get("held_back")
                             else "the run's checked corrections are merged; this point about a published value is open."),
              "", "### Question", "", q.get("why") or "", "",
              "If nobody decides, the published record stays as it is and the record shows this question.", "",
              "### Evidence", ""]
        for k in ("official_url", "secondary_url"):
            if r.get(k):
                L.append("- %s: %s" % (k, r[k]))
        for sub in ("extractions", "checks", "extractions-blind"):
            if (RUNS / run / sub / ("%s.json" % q["subject"])).is_file():
                L.append("- %s: %sruns/%s/%s/%s.json" % (sub, blob, run, sub, q["subject"]))
        L += ["", "### How to decide", "",
              "A maintainer comments one decision; it is applied at the start of the next pipeline run "
              "(`python3 tools/pipeline.py questions --apply`), recorded in `data/history.jsonl` and linked here.", "",
              "- `decide: keep`: the published values stay.",
              "- `decide: accept`: apply the run's extraction for this record (when its change was held back and the "
              "record has not changed since).",
              "- `decide: set <field> = <value>`, one line per field, with `source: <URL>`: set values yourself.",
              "- `decide: in` or `decide: out`, with a reason: a scope decision.", "",
              "Anyone can add evidence in the comments."]
    elif q["kind"] == "host":
        ev = q.get("evidence") or {}
        L += ["**Host:** %s (jurisdiction %s)" % (q["subject"], q.get("code")), "", "### Question", "",
              "Does a public body run this host, or use it as its own channel (AGENTS.md section 7.6)? %s" % (q.get("why") or ""), ""]
        if q.get("operator"):
            L.append("Operator check: %s" % q["operator"])
        if ev.get("url"):
            L.append("Checked page: %s%s" % (ev["url"], (' ("%s")' % ev["quote"]) if ev.get("quote") else ""))
        if q.get("records"):
            L.append("Quoted for: %s" % ", ".join(q["records"]))
        L += ["", "Until decided, quotes from this host count as secondary.", "", "### How to decide", "",
              "- `decide: official`, optionally with `operator: <who runs it>`",
              "- `decide: not official`"]
    elif q["kind"] == "hosts":
        L += ["These hosts are in `pipeline/official-sites.json` as official seeds (taken from records' official_url), "
              "and no person has confirmed who runs them (AGENTS.md section 7.6). A host reviewer looked up each "
              "site's operator; the suggestion is the reviewer's, the decision is yours. Open the page before deciding: a quote "
              "may be shortened or paraphrased by the tool the reviewer read it with.", "",
              "| Jurisdiction | Host | Who runs it (reviewer's finding) | Page | Suggestion |", "|---|---|---|---|---|"]
        for h in q.get("hosts") or []:
            who = (h.get("operator") or "not found").replace("|", "/")
            if h.get("quote"):
                who += ': "%s"' % h["quote"].replace("|", "/").replace("\n", " ")[:200]
            L.append("| %s | `%s` | %s | %s | %s |" % (h["code"], h["host"], who, h.get("url") or "-",
                                                        h.get("suggestion") or "-"))
        L += ["", "### How to decide", "",
              "In one comment, one line per host you decide (leave out the ones you are unsure of):", "",
              "- `decide: official <host>`, optionally followed by the operator in parentheses",
              "- `decide: not official <host>`", "",
              "Each line is recorded with `pipeline.py hosts --add` (you as the decider, this comment as the evidence). "
              "The issue stays open until every host in it is decided; hosts without a decision keep counting as "
              "official seeds."]
    else:
        L += ["**Run:** [%s](%sruns/%s/report.md)" % (q["subject"], blob, q["subject"]), "",
              "Check each record against its stored sources (the run report and the record page link them):", ""]
        L += ["- [ ] %s %s" % (rid, (by.get(rid) or {}).get("short_title") or "") for rid in q["records"]]
        L += ["", "### How to report", "", "One line per record in a comment: `ok <ID> <note>` or `problem <ID> <note>`. "
              "Each line becomes a `human-checked` event in the record's history; a problem queues the record for a refresh run."]
    L += ["", "<!-- question-key: %s -->" % q["key"]]
    return "\n".join(L)


def ensure_labels(repo):
    for name, color, desc in (("question", "d876e3", "A question for a maintainer from the pipeline"),
                              ("question:record", "c5def5", "A record's open question"),
                              ("question:host", "c5def5", "Is this host an official site?"),
                              ("question:hosts", "c5def5", "Which of these hosts are official sites? (a batch)"),
                              ("question:sample", "c5def5", "Human sample of a run")):
        gh("label", "create", name, "--repo", repo, "--color", color, "--description", desc, "--force")


def written_by_agent(c):
    """A comment an agent or a bot wrote: it carries the agent marker (AGENTS.md section 4, rule 11) or comes from a
    bot account. Such a comment is never a maintainer's decision, even when it was posted with a maintainer's login."""
    return "every-ai-policy-ever:agent" in (c.get("body") or "") or (c.get("user") or {}).get("type") == "Bot"


def parse_decisions(comments, kind):
    """The latest decision by a maintainer, as (comment, [parsed lines]); None when there is none."""
    for c in reversed(comments):
        if c.get("author_association") not in DECIDERS or written_by_agent(c):
            continue
        body = c.get("body") or ""
        if kind == "sample":
            lines = re.findall(r"(?im)^\s*(ok|problem)\s+(\S+)\s*:?\s*(.*)$", body)
        else:
            lines = re.findall(r"(?im)^\s*(decide|source|operator)\s*:\s*(.+?)\s*$", body)
        if lines and (kind == "sample" or any(k.lower() == "decide" for k, _ in lines)):
            return c, lines
    return None


HOST_LINE = re.compile(r"(?im)^\s*decide\s*:\s*(official|not official)\s+`?([a-z0-9.-]+\.[a-z]{2,})`?\s*(?:\((.+?)\))?\s*$")


def parse_host_batch(comments):
    """{host: (status, operator, comment)} from every maintainer comment on a batch issue; a later line wins."""
    out = {}
    for c in comments:
        if c.get("author_association") not in DECIDERS or written_by_agent(c):
            continue
        for status, host, op in HOST_LINE.findall(c.get("body") or ""):
            out[strip_www(host.lower())] = (status.lower(), op.strip() or None, c)
    return out


def apply_record_decision(q, comment, lines, db, dry):
    rid, run_id = q["subject"], q["run_id"]
    num = q.get("issue")
    who = (comment.get("user") or {}).get("login") or "maintainer"
    decides = [v for k, v in lines if k.lower() == "decide"]
    source = next((v for k, v in lines if k.lower() == "source"), None)
    note = "decided in issue #%s by %s: %s" % (num, who, comment.get("html_url"))
    first = decides[0].strip()
    if first.lower() in ("keep",) or (first.lower() == "accept" and not q.get("held_back")):
        if not dry:
            history.append([history.event(rid, "human-decision", run_id=q["key"], new="keep", reason=note,
                                          tool="GitHub issue #%s" % num, model=who)])
        return "kept the published values"
    if first.lower() in ("in", "out") or re.match(r"(?i)^(in|out)\b", first):
        dec = first.split()[0].lower()
        reason = first[len(dec):].strip(" :,-") or "see issue #%s" % num
        if not dry:
            cmd_log_scope(argparse.Namespace(run=None, id=rid, decision=dec, note="%s (issue #%s)" % (reason, num), by=who))
            history.append([history.event(rid, "human-decision", run_id=q["key"], new="scope %s" % dec, reason=note,
                                          tool="GitHub issue #%s" % num, model=who)])
        return "scope decision: %s" % dec
    updates = {}
    if first.lower() == "accept":
        later = [e for e in history.load() if e["record_id"] == rid and e.get("run_id") not in (run_id, q["key"])]
        order = run_order()
        if any(e.get("run_id") in order and order.index(e["run_id"]) > order.index(run_id) for e in later):
            return "not applied: the record changed after run %s; decide with `set` instead" % run_id
        ex = read_json(RUNS / run_id / "extractions" / ("%s.json" % rid), {}) or {}
        updates = {k: v for k, v in (ex.get("record") or {}).items() if k in RECORD_FIELDS and k not in SET_BY_SCRIPT
                   and k != "verification"}
    else:
        for d in decides:
            m = re.match(r"(?i)^set\s+([a-z_]+)\s*=\s*(.+)$", d)
            if not m or m.group(1) not in RECORD_FIELDS or m.group(1) in SET_BY_SCRIPT or m.group(1) == "verification":
                return "not applied: cannot read %r (use keep, accept, in, out, or set <field> = <value>)" % d
            val = m.group(2).strip()
            try:
                val = json.loads(val)
            except ValueError:
                val = None if val.lower() == "null" else val
            updates[m.group(1)] = val
    if not updates:
        return "not applied: nothing to change"
    if dry:
        return "would set %s" % ", ".join(sorted(updates))
    cur = {r["id"]: r for r in db["records"]}[rid]
    vnote = ((cur.get("verification") or {}).get("note") or "").rstrip()
    upd = dict(updates, id=rid, verification={"verified_on": today(), "note": (vnote + " Human decision in issue #%s (%s)%s."
                                                                                % (num, who, ": source " + source if source else "")).strip()})
    src = {"provenance": {"date": today(), "agent": "GitHub issue #%s" % num, "model": who, "scope": note,
                          "run_id": q["key"]},
           "records": [], "updates": [upd],
           "history_context": {rid: {"reason": note, "evidence": [{"url": source}] if source else [],
                                     "fields": {k: {"reason": note, "evidence": [{"url": source}] if source else []}
                                                for k in updates}}}}
    tmp = Path(tempfile.mkstemp(suffix=".json")[1])
    tmp.write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    import merge  # noqa: E402  (same folder)
    rc = merge.main([str(tmp)])
    tmp.unlink()
    if rc:
        return "not applied: merge.py refused it (see its output)"
    history.append([history.event(rid, "human-decision", run_id=q["key"], new="set %s" % ", ".join(sorted(updates)),
                                  reason=note, tool="GitHub issue #%s" % num, model=who)])
    return "set %s" % ", ".join(sorted(updates))


def cmd_questions(args):
    if (args.sync or args.apply) and not args.dry_run and not can_write(github_repo()):
        return not_a_maintainer(github_repo(), "questions --sync/--apply")
    db = load_db()
    by = {r["id"]: r for r in db["records"]}
    reg = read_json(QUESTIONS, {}) or {}
    reg.setdefault("about", "Open questions the pipeline cannot settle, each a GitHub issue (AGENTS.md section 7.7). "
                            "Written by tools/pipeline.py questions; decisions are applied with --apply and recorded "
                            "in data/history.jsonl.")
    items = OrderedDict((q["key"], q) for q in reg.get("questions") or [])
    found = collect_questions(db)
    repo = None
    if args.apply:
        repo = github_repo()
        applied = 0
        for key, q in items.items():
            if q.get("state") != "open" or not q.get("issue"):
                continue
            comments = json.loads(gh("api", "repos/%s/issues/%s/comments" % (repo, q["issue"]), "--paginate") or "[]")
            if q["kind"] == "hosts":
                pend = {strip_www(e["host"]) for e in load_sites().get("sites") or [] if pending_site(e)}
                mine = {h["host"]: h for h in q.get("hosts") or []}
                done = []
                for host, (status, op, c) in parse_host_batch(comments).items():
                    if host in mine and host in pend:
                        who_ = (c.get("user") or {}).get("login") or "maintainer"
                        if not args.dry_run:
                            cmd_hosts(argparse.Namespace(add=host, code=mine[host]["code"], status=status, by=who_,
                                                         operator=op or mine[host].get("operator"), kind=None,
                                                         evidence_url=c.get("html_url"), quote=None, pending=False,
                                                         note="decided in issue #%s (host review %s)" % (q["issue"], q["subject"])))
                        done.append("%s %s" % (host, status))
                left = [h for h in mine if h in pend and h not in {d.split()[0] for d in done}]
                if done:
                    print("#%-5s %-40s %s" % (q["issue"], key, "; ".join(done)))
                    applied += len(done)
                    if not args.dry_run:
                        if left:
                            gh("issue", "comment", str(q["issue"]), "--repo", repo, "--body",
                               "Applied by `pipeline.py questions --apply`: %s. Still open: %s." % (", ".join(done), ", ".join(left)))
                        else:
                            q.update(state="decided", closed=today(), resolution="; ".join(done))
                            gh("issue", "close", str(q["issue"]), "--repo", repo, "--comment",
                               "Applied by `pipeline.py questions --apply`: %s. Recorded in pipeline/official-sites.json; "
                               "the records that quote these hosts change in their next refresh run." % ", ".join(done))
                continue
            got = parse_decisions(comments, q["kind"])
            if not got:
                continue
            comment, lines = got
            who = (comment.get("user") or {}).get("login") or "maintainer"
            if q["kind"] in ("record", "candidate"):
                result = apply_record_decision(q, comment, lines, db, args.dry_run)
            elif q["kind"] == "host":
                dec = next(v for k, v in lines if k.lower() == "decide").strip().lower()
                op = next((v for k, v in lines if k.lower() == "operator"), None) or q.get("operator")
                if dec not in ("official", "not official"):
                    result = "not applied: use `decide: official` or `decide: not official`"
                else:
                    result = "host %s" % dec
                    if not args.dry_run:
                        cmd_hosts(argparse.Namespace(add=q["subject"], code=q.get("code"), status=dec, by=who, operator=op,
                                                     kind=None, evidence_url=comment.get("html_url"), quote=None,
                                                     note="decided in issue #%s" % q["issue"], pending=False))
            else:
                done = []
                for res, rid, note in lines:
                    if rid in q["records"] and not args.dry_run:
                        cmd_log_human(argparse.Namespace(run=q["subject"], id=rid, result=res.lower(),
                                                         note="%s (issue #%s)" % (note, q["issue"]), by=who))
                    done.append("%s %s" % (rid, res.lower()))
                result = "logged " + ", ".join(done)
            print("#%-5s %-40s %s" % (q["issue"], key, result))
            if result.startswith("not applied"):
                if not args.dry_run:
                    gh("issue", "comment", str(q["issue"]), "--repo", repo, "--body", "Not applied: %s" % result[13:])
                continue
            applied += 1
            if not args.dry_run and q["kind"] != "sample":
                q.update(state="decided", closed=today(), resolution=result)
                gh("issue", "close", str(q["issue"]), "--repo", repo, "--comment",
                   "Applied by `pipeline.py questions --apply`: %s. Recorded in %s." % (
                       result, "pipeline/official-sites.json; the records that quote this host change in their next "
                       "refresh run" if q["kind"] == "host" else "data/history.jsonl"))
        if not args.dry_run:
            db = load_db()
            found = collect_questions(db)  # decisions may have settled samples and hosts
        print("%d decision(s) %s." % (applied, "found (dry run)" if args.dry_run else "applied"))
    for key, q in found.items():  # new questions, and new facts about open ones
        old = items.get(key)
        if old and old.get("state") == "open":
            # a record question has no title of its own; keep the one its issue was given
            old.update({k: v for k, v in q.items() if k not in ("issue", "url", "opened", "state")
                        and not (k == "title" and v is None)})
        elif not old:
            items[key] = dict(q, state="open", issue=None, url=None, opened=today(), closed=None, resolution=None)
    for key, q in items.items():  # open questions nothing implies any more are settled
        if q.get("state") == "open" and key not in found:
            q.update(state="settled", closed=today(), resolution=q.get("resolution") or "settled by a later run or decision")
    if args.sync:
        repo = repo or github_repo()
        if not args.dry_run:
            ensure_labels(repo)
        live = None  # the titles the open issues have on GitHub now, read once
        for key, q in items.items():
            if q["state"] == "open" and not q.get("issue"):
                title, body = question_title(q, by), question_body(q, by, repo)
                if args.dry_run:
                    print("would open: %s" % title)
                    continue
                url = gh("issue", "create", "--repo", repo, "--title", title, "--body-file", "-", "--label", "question",
                         "--label", "question:%s" % ("record" if q["kind"] == "candidate" else q["kind"]),
                         input_text=body).strip().splitlines()[-1]
                q.update(issue=int(url.rstrip("/").rsplit("/", 1)[1]), url=url, title=title)
                print("opened #%s %s" % (q["issue"], title))
            elif q["state"] == "open" and q.get("issue"):
                title = question_title(q, by)
                if live is None:
                    live = {i["number"]: i["title"] for i in json.loads(
                        gh("issue", "list", "--repo", repo, "--state", "all", "--label", "question", "--limit", "1000",
                           "--json", "number,title") or "[]")}
                if live.get(q["issue"], title) != title:
                    if args.dry_run:
                        print("would retitle #%s: %s" % (q["issue"], title))
                        continue
                    gh("issue", "edit", str(q["issue"]), "--repo", repo, "--title", title)
                    q["title"] = title
            elif q["state"] == "settled" and q.get("issue") and not q.get("closed_on_github"):
                if args.dry_run:
                    print("would close #%s (%s)" % (q["issue"], q["resolution"]))
                    continue
                gh("issue", "close", str(q["issue"]), "--repo", repo, "--comment",
                   "Closed by `pipeline.py questions --sync`: %s." % q["resolution"])
                q["closed_on_github"] = True
    if (args.sync or args.apply) and not args.dry_run:  # listing only reads
        reg["questions"] = list(items.values())
        write_json(QUESTIONS, reg)
        build.save(build.load())  # open questions show in records.js, the CSV, the record pages and the exports
    st = Counter(q["state"] for q in items.values())
    kinds = Counter(q["kind"] for q in items.values() if q["state"] == "open")
    print("Questions: %s; open by kind: %s%s" % (", ".join("%s %d" % kv for kv in st.most_common()) or "none",
                                                 ", ".join("%s %d" % kv for kv in kinds.most_common()) or "-",
                                                 " (dry run: nothing written)" if args.dry_run else ""))
    if not args.sync and not args.apply:
        for q in items.values():
            if q["state"] == "open":
                print("  %-7s %-34s %s" % ("#%s" % q["issue"] if q.get("issue") else "-", q["key"][:34],
                                           (q.get("why") or "")[:90]))
    return 0


# ----------------------------------------------------------------------------- suggestions and documents from users

LEADS = ROOT / "pipeline" / "leads.json"
BODY_TO_TYPE = {"legislature": "legislature", "government": "executive", "ministry": "ministries",
                "ai regulator": "ai-bodies", "supervisory": "supervisors", "election": "elections",
                "intergovernmental": "repository"}
ATTACHMENT = re.compile(r"https://github\.com/user-attachments/(?:files|assets)/[^\s)\]>\"']+")


def form_fields(body):
    """The answers of a GitHub issue form: {heading: value}; '_No response_' is empty."""
    parts = re.split(r"^###\s+(.+?)\s*$", body or "", flags=re.M)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        v = parts[i + 1].strip()
        out[parts[i].strip().lower()] = "" if v == "_No response_" else v
    return out


def lead_cell(code, issued_by, frame, override=None):
    cells = {cell_id(j, t) for j, t, c in frame_cells(frame)}
    if override:
        return override if override in cells else None
    kind = next((t for k, t in BODY_TO_TYPE.items() if k in (issued_by or "").lower()), "executive")
    j = next((x for x in frame.get("jurisdictions") or [] if x["code"] == (code or "").strip().upper()), None)
    if not j:
        return None
    for t in (kind, "repository", "executive", "legislature"):
        if t in j["cells"]:
            return "%s/%s" % (j["code"], t)
    return None


def load_leads():
    reg = read_json(LEADS, {}) or {}
    reg.setdefault("about", "Leads for the pipeline: instruments suggested in GitHub issues and accepted by a maintainer, "
                            "and leads a maintainer added with `pipeline.py leads --add`. `pipeline.py new --type discover "
                            "--leads pipeline/leads.json` takes the queued ones. Written by tools/pipeline.py intake and leads.")
    reg.setdefault("leads", [])
    return reg


def next_lead_id(leads):
    n = max([int(l["id"][1:]) for l in leads if re.match(r"^L\d+$", l.get("id") or "")] + [0])
    return "L%03d" % (n + 1)


def lead_name(l):
    return " ".join(x for x in (l.get("id"), "#%s" % l["issue"] if l.get("issue") else None) if x) or (l.get("lead") or "")[:40]


def cmd_leads(args):
    """List the leads, add one by hand, or drop a queued one (AGENTS.md section 7.8)."""
    reg = load_leads()
    leads = reg["leads"]
    if args.attach:
        l = next((x for x in leads if x.get("id") == args.attach), None)
        if not l or l.get("state") != "queued":
            raise SystemExit("%s is not a queued lead" % args.attach)
        if not (args.provided and args.by and (args.url or l.get("url"))):
            raise SystemExit("--attach needs --provided FILE and --by (and --url when the lead has none)")
        if args.dry_run:
            print("would store %s with %s (dry run: nothing written)" % (args.provided, args.attach))
            return 0
        import archive  # noqa: E402  (same folder)
        f = archive.store_provided_lead(args.attach, args.provided, args.url or l["url"], args.by, args.confirmed_by,
                                        args.issue, known=[(l.get("provided") or {}).get("sha256")])
        if not f:
            print("%s already has this file (same SHA-256); nothing stored." % args.attach)
            return 0
        l["provided"] = f
        write_json(LEADS, reg)
        print("Stored %s with lead %s (SHA-256 %s); the run that follows the lead up uses it." % (f["path"], args.attach,
                                                                                               f["sha256"]))
        return 0
    if args.drop:
        l = next((x for x in leads if x.get("id") == args.drop), None)
        if not l or l.get("state") != "queued":
            raise SystemExit("%s is not a queued lead" % args.drop)
        if not (args.by and args.why):
            raise SystemExit("--drop needs --by and --why")
        l.update(state="dropped", dropped_by=args.by, dropped_on=today(), drop_reason=args.why)
        if not args.dry_run:
            write_json(LEADS, reg)
        print("%s dropped%s" % (args.drop, " (dry run: nothing written)" if args.dry_run else ""))
        return 0
    if not args.add:
        for l in leads:
            where = l.get("record_id") if l.get("state") in ("refresh-queued", "checked", "included") else l.get("cell")
            src = "#%s" % l["issue"] if l.get("issue") else l.get("added_by") or ""
            print("%-5s %-15s %-22s %-16s %s" % (l.get("id") or "-", l.get("state"), where or "", src[:16],
                                                 (l.get("lead") or l.get("url") or "")[:70]))
        st = Counter(l.get("state") for l in leads)
        print("Leads: %s" % (", ".join("%s %d" % kv for kv in st.most_common()) or "none"))
        return 0
    if not (args.lead and args.by):
        raise SystemExit("--add needs --lead TITLE and --by NAME")
    if not (args.url or args.seen_in):
        raise SystemExit("--add needs --url (the official page) or --seen-in (where the instrument was seen), or both")
    if args.provided and (args.record or not args.url):
        raise SystemExit("--provided needs --url, the official page the document comes from; for an existing record "
                         "use tools/archive.py --provide")
    for u in (args.url, args.seen_in):
        if u and not re.match(r"^https?://", u):
            raise SystemExit("not a web address: %s" % u)
    db = load_db()
    by = {r["id"]: r for r in db["records"]}
    nu, nt = norm_url(args.url), norm_title(args.lead)
    for l in leads:
        if l.get("state") in ("dropped", "rejected"):
            continue
        if (nu and norm_url(l.get("url")) == nu) or (nt and norm_title(l.get("lead")) == nt):
            raise SystemExit("Already a lead: %s (%s%s)" % (l.get("id") or "#%s" % l.get("issue"), l.get("state"),
                                                            ", " + l["record_id"] if l.get("record_id") else ""))
    lid = next_lead_id(leads)
    if args.record:
        rid = args.record.strip().upper()
        if rid not in by:
            raise SystemExit("No record %s" % rid)
        line = {"date": today(), "run_id": "lead %s" % lid, "record_id": rid,
                "why": "%s, added by %s: %s" % (args.why or args.lead, args.by, args.url or args.seen_in)}
        lead = {"id": lid, "lead": args.lead, "url": args.url, "seen_in": args.seen_in, "record_id": rid,
                "why": args.why, "state": "refresh-queued", "added_by": args.by, "added": today()}
        if not args.dry_run:
            with open(REQUESTS, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        msg = "%s: news about %s, queued for its next refresh run" % (lid, rid)
    else:
        hit = next((r["id"] for r in db["records"] for u in (r.get("official_url"), r.get("secondary_url"))
                    if nu and u and norm_url(u) == nu), None)
        if hit:
            raise SystemExit("%s is a source of %s; for news about it use --record %s" % (args.url, hit, hit))
        cell = lead_cell(args.code, args.issued_by, load_frame(), args.cell)
        if not cell:
            raise SystemExit("Give --cell CODE/type (a cell of pipeline/frame.json) or --code with a jurisdiction "
                             "in the frame")
        lead = {"id": lid, "lead": args.lead, "cell": cell, "url": args.url, "seen_in": args.seen_in, "why": args.why,
                "state": "queued", "added_by": args.by, "added": today()}
        if args.provided and not args.dry_run:
            import archive  # noqa: E402  (same folder)
            lead["provided"] = archive.store_provided_lead(lid, args.provided, args.url, args.by, args.confirmed_by,
                                                           args.issue)
            msg_doc = " with the provided document %s" % lead["provided"]["path"]
        msg = "%s queued in %s%s; `new --type discover --leads pipeline/leads.json` starts a run on the queued leads" % (
            lid, cell, msg_doc if args.provided and not args.dry_run else "")
    leads.append({k: v for k, v in lead.items() if v})
    if not args.dry_run:
        write_json(LEADS, reg)
    print(msg + (" (dry run: nothing written)" if args.dry_run else ""))
    return 0


FIELD_CAP = {"title": 200, "why it belongs in the register": 500, "official url": 500}


def intake_triage(repo, reg, db):
    """Undecided suggestions and documents, with what a maintainer may want to look at before deciding (AGENTS.md
    section 7.9). It only reads GitHub and prints; it decides nothing and posts nothing."""
    official, rejected = site_hosts(load_sites())
    by_url = {}
    for r in db["records"]:
        for u in (r.get("official_url"), r.get("secondary_url")):
            if u:
                by_url.setdefault(norm_url(u), r["id"])
    lead_by_url = {norm_url(l["url"]): l.get("id") or "#%s" % l.get("issue") for l in reg["leads"]
                   if l.get("url") and l.get("state") not in ("dropped", "rejected")}
    week, month = [(dt.date.today() - dt.timedelta(days=d)).isoformat() for d in (7, 30)]
    authors, shown = {}, 0
    for label in ("source-suggestion", "document"):
        issues = json.loads(gh("issue", "list", "--repo", repo, "--state", "open", "--label", label, "--limit", "200",
                               "--json", "number,title,body,author,createdAt") or "[]")
        for it in issues:
            num = it["number"]
            if parse_decisions(json.loads(gh("api", "repos/%s/issues/%s/comments" % (repo, num), "--paginate") or "[]"),
                               "record"):
                continue
            info = json.loads(gh("api", "repos/%s/issues/%s" % (repo, num)) or "{}")
            login = (it.get("author") or {}).get("login") or "?"
            if login not in authors:
                user = json.loads(gh("api", "users/%s" % login) or "{}")
                recent = json.loads(gh("issue", "list", "--repo", repo, "--state", "all", "--author", login, "--search",
                                       "created:>=%s" % week, "--limit", "100", "--json", "number") or "[]")
                authors[login] = ((user.get("created_at") or "")[:10], len(recent))
            created, recent = authors[login]
            f = form_fields(it.get("body"))
            signals = []
            who = f.get("submitted by", "")
            if who and not who.lower().startswith("a person"):
                signals.append("declared: %s%s" % (who, " (%s)" % f["agent or tool"][:80] if f.get("agent or tool") else ""))
            if (info.get("user") or {}).get("type") == "Bot":
                signals.append("bot account")
            if (info.get("performed_via_github_app") or {}).get("name"):
                signals.append("posted via the app %s" % info["performed_via_github_app"]["name"])
            if created and created >= month:
                signals.append("account created %s" % created)
            if recent > 3:
                signals.append("%d issues by this account in 7 days" % recent)
            url = f.get("official url", "").strip()
            code = (f.get("jurisdiction code") or f.get("record id", "").rsplit("-", 1)[0]).strip().upper()
            host = (urllib.parse.urlsplit(url).hostname or "").lower() if re.match(r"^https?://", url) else ""
            if not host:
                signals.append("no usable URL")
            elif not official_host(host, code, official, rejected):
                signals.append("not an official host for %s: %s" % (code or "?", host))
            if host and label == "source-suggestion" and not f.get("existing record") and norm_url(url) in by_url:
                signals.append("already a source of %s" % by_url[norm_url(url)])
            if host and norm_url(url) in lead_by_url:
                signals.append("already lead %s" % lead_by_url[norm_url(url)])
            shown += 1
            print("#%-5s %-17s %s  @%s (%s)" % (num, label, it.get("createdAt", "")[:10], login,
                                               info.get("author_association") or "?"))
            print("       %s" % (f.get("title") or f.get("record id") or it.get("title") or "")[:100])
            print("       %s" % ("; ".join(signals) if signals else "no signals"))
    print("Undecided: %d" % shown)
    return 0


def cmd_intake(args):
    """Suggestions and provided documents from GitHub issues (AGENTS.md section 7.8)."""
    import archive  # noqa: E402  (same folder)
    import tempfile as _tf
    repo = github_repo()
    reg = load_leads()
    leads = reg["leads"]
    if args.triage:
        return intake_triage(repo, reg, load_db())
    if not args.dry_run and not can_write(repo):
        return not_a_maintainer(repo, "intake")
    known = {l.get("issue") for l in leads if l.get("issue")}
    frame, db = load_frame(), load_db()
    by = {r["id"]: r for r in db["records"]}
    done = []

    def say(num, text, close=False):
        if args.dry_run:
            return
        gh("issue", "comment", str(num), "--repo", repo, "--body", text)
        if close:
            gh("issue", "close", str(num), "--repo", repo)

    for label in ("source-suggestion", "document"):
        issues = json.loads(gh("issue", "list", "--repo", repo, "--state", "open", "--label", label, "--limit", "200",
                               "--json", "number,title,body,author,url") or "[]")
        for it in issues:
            num = it["number"]
            if num in known:
                continue
            comments = json.loads(gh("api", "repos/%s/issues/%s/comments" % (repo, num), "--paginate") or "[]")
            got = parse_decisions(comments, "record")
            if not got:
                continue
            comment, lines = got
            who = (comment.get("user") or {}).get("login") or "maintainer"
            dec = next(v for k, v in lines if k.lower() == "decide").strip()
            if dec.lower().startswith("reject"):
                reason = dec[6:].strip(" :,-") or "outside the register's scope"
                say(num, "Not included: %s. (Decided by @%s.)" % (reason, who), close=True)
                done.append("#%s rejected" % num)
                continue
            if not dec.lower().startswith("accept"):
                say(num, "Could not read the decision %r; use `decide: accept` or `decide: reject <reason>`." % dec)
                continue
            f = {k: v[:FIELD_CAP.get(k, 500)] for k, v in form_fields(it.get("body")).items()}
            if label == "source-suggestion":
                url = f.get("official url", "").strip()
                rid = f.get("existing record", "").strip().upper()
                if rid and rid in by:
                    line = {"date": today(), "run_id": "issue #%s" % num, "record_id": rid,
                            "why": "news suggested in issue #%s and accepted by %s: %s" % (num, who, url)}
                    if not args.dry_run:
                        with open(REQUESTS, "a", encoding="utf-8") as fh:
                            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
                    leads.append({"id": next_lead_id(leads), "issue": num, "url": url, "record_id": rid,
                                  "state": "refresh-queued",
                                  "accepted_by": who, "added": today()})
                    say(num, "Accepted by @%s: %s goes into the next refresh run, which checks this source." % (who, rid))
                    done.append("#%s queued for a refresh of %s" % (num, rid))
                    continue
                override = next((v.strip() for k, v in lines if k.lower() == "cell"), None)
                cell = lead_cell(f.get("jurisdiction code"), f.get("issued by"), frame, override)
                if not cell:
                    say(num, "Accepted, but the jurisdiction code %r is not in the coverage frame. Add a line "
                             "`cell: <CODE>/<type>` to the decision (types: legislature, gazette, executive, ministries, "
                             "ai-bodies, elections, supervisors, repository)." % f.get("jurisdiction code"))
                    continue
                leads.append({"id": next_lead_id(leads), "lead": f.get("title") or it["title"], "cell": cell,
                              "url": url, "issue": num,
                              "seen_in": "issue #%s" % num, "why": f.get("why it belongs in the register"),
                              "state": "queued", "accepted_by": who, "added": today()})
                say(num, "Accepted by @%s and queued for the next pipeline run (cell %s). This issue is closed when the "
                         "record is in the register." % (who, cell))
                done.append("#%s queued as a lead (%s)" % (num, cell))
            else:
                rid = f.get("record id", "").strip().upper()
                url = f.get("official url", "").strip()
                links = ATTACHMENT.findall(f.get("the document", "") or it.get("body") or "")
                # an instrument without a record: the document is stored with a new lead, which the next run follows up
                override = next((v.strip() for k, v in lines if k.lower() == "cell"), None)
                cell = None if rid in by else lead_cell(f.get("jurisdiction code"), None, frame, override)
                problem = ("no attached file was found in the issue" if not links else None if rid in by or cell else
                           "the record ID %r does not exist" % rid if rid else
                           "give the record ID, or for an instrument without a record its title and a jurisdiction code "
                           "of the coverage frame (or `cell: <CODE>/<type>` in the decision)")
                if problem:
                    say(num, "Cannot store it: %s." % problem)
                    continue
                if args.dry_run:
                    done.append("#%s would store %s for %s" % (num, links[0], rid if rid in by else "a lead in " + cell))
                    continue
                provider = (it.get("author") or {}).get("login")
                with _tf.TemporaryDirectory() as tmp:
                    name = urllib.parse.unquote(links[0].rsplit("/", 1)[-1]) or "document.pdf"
                    path = Path(tmp) / re.sub(r"[^A-Za-z0-9._-]", "_", name)
                    req = urllib.request.Request(links[0], headers={"User-Agent": "every-ai-policy-ever intake"})
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        path.write_bytes(resp.read())
                    if rid in by:
                        stored = archive.store_provided(db, rid, path, url, provider, confirmed_by=who, issue=num,
                                                        source_url=links[0], note="provided in issue #%s" % num)
                    else:
                        lid = next_lead_id(leads)
                        stored = archive.store_provided_lead(lid, path, url, provider, confirmed_by=who, issue=num,
                                                             source_url=links[0], note="provided in issue #%s" % num)
                if rid not in by:
                    leads.append({"id": lid, "lead": f.get("title") or it["title"], "cell": cell, "url": url, "issue": num,
                                  "seen_in": "issue #%s" % num, "provided": stored, "state": "queued",
                                  "accepted_by": who, "added": today()})
                    say(num, "Stored as `%s` (SHA-256 `%s`), provided by @%s and confirmed by @%s, and queued as lead %s "
                             "for the next pipeline run (cell %s), which uses it as the official text. This issue is closed "
                             "when the record is in the register." % (stored["path"], stored["sha256"], provider, who,
                                                                       lid, cell))
                    done.append("#%s stored with lead %s (%s)" % (num, lid, cell))
                    continue
                build.save(db)
                if stored:
                    with open(REQUESTS, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"date": today(), "run_id": "issue #%s" % num, "record_id": rid,
                                             "why": "official text provided in issue #%s" % num}) + "\n")
                    say(num, "Stored as `%s` (SHA-256 `%s`), provided by @%s and confirmed by @%s. The next refresh run "
                             "of %s reads it." % (stored["path"], stored["sha256"], stored["provided_by"], who, rid), close=True)
                    done.append("#%s stored for %s" % (num, rid))
                else:
                    say(num, "This file is already stored for %s." % rid, close=True)
    # suggestions about existing records: close them once a pipeline run has checked the record again
    order = run_order()
    for l in leads:
        if l.get("state") != "refresh-queued":
            continue
        hit = next((e for e in history.load() if e["record_id"] == l.get("record_id") and e.get("run_id") in order
                    and e.get("event") in ("changed", "re-verified") and (e.get("date") or "") >= (l.get("added") or "")
                    and (RUNS / e["run_id"] / "pass.json").is_file()
                    and l["record_id"] in {u.get("id") for u in (read_json(RUNS / e["run_id"] / "pass.json", {}) or {})
                                           .get("updates") or [] if set(u) - {"id", "related"}}), None)
        if hit:
            l.update(state="checked", run_id=hit["run_id"])
            if l.get("issue"):
                say(l["issue"], "Checked in run %s: %s. The record's history shows what changed." % (hit["run_id"], l["record_id"]),
                    close=True)
            done.append("lead %s checked in %s" % (lead_name(l), hit["run_id"]))
    # leads a run took: close their issues once the run is merged
    for l in leads:
        if l.get("state") != "in-run" or not l.get("run_id"):
            continue
        d = RUNS / l["run_id"]
        p = read_json(d / "pass.json", {}) or {}
        if (read_json(d / "run.json", {}) or {}).get("status") != "merged":
            continue
        cand = next((c for c in (read_json(d / "candidates.json", {}) or {}).get("candidates") or []
                     if (l.get("id") and c.get("lead") == l["id"]) or (l.get("issue") and c.get("issue") == l["issue"])
                     or (l.get("url") and norm_url(c.get("url")) == norm_url(l["url"]))), None)
        rid = (p.get("assigned") or {}).get(cand["cand_id"]) if cand else None
        if rid:
            l.update(state="included", record_id=rid)
            if l.get("issue"):
                say(l["issue"], "Included as %s in run %s." % (rid, l["run_id"]), close=True)
            done.append("lead %s included as %s" % (lead_name(l), rid))
        else:
            l.update(state="not-added")
            if l.get("issue"):
                why = next((x.get("why") for x in (p.get("not_added") or []) + (p.get("needs_human") or [])
                            if cand and x.get("cand_id") == cand["cand_id"]), "the run found no official source for it")
                say(l["issue"], "Run %s did not add it: %s" % (l["run_id"], (why or "")[:500]), close=False)
            done.append("lead %s not added" % lead_name(l))
    if not args.dry_run:
        write_json(LEADS, reg)
        build.save(build.load())
    for x in done:
        print(x)
    st = Counter(l.get("state") for l in leads)
    print("Leads: %s%s" % (", ".join("%s %d" % kv for kv in st.most_common()) or "none",
                           " (dry run: nothing written)" if args.dry_run else ""))
    return 0


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Pipeline scripts (AGENTS.md sections 5 to 7).")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("new", help="create a run")
    s.add_argument("--type", required=True)
    s.add_argument("--scope")
    s.add_argument("--label", help="short name for the run ID")
    s.add_argument("--tool")
    s.add_argument("--model")
    s.add_argument("--days", type=int)
    s.add_argument("--limit", type=int, help="records taken from the queue: refresh 25, compare 5")
    s.add_argument("--large", action="store_true", help="allow a run larger than MAX_RUN")
    s.add_argument("--group-size", type=int, default=10)
    s.add_argument("--leads", help="discover: follow up only these leads, a JSON file {\"leads\": [{\"lead\", \"cell\", \"seen_in\", \"url\"}]}")
    s = sub.add_parser("menu", help="what is ready to run now")
    s = sub.add_parser("board", help="the project status; --sync writes it into the pinned issue")
    s.add_argument("--sync", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--offline", action="store_true", help="do not read GitHub")
    s = sub.add_parser("status")
    s.add_argument("--run", required=True)
    s = sub.add_parser("stage", help="record the tool and model of a stage")
    s.add_argument("--run", required=True)
    s.add_argument("--stage", required=True)
    s.add_argument("--tool", required=True)
    s.add_argument("--model", required=True)
    s.add_argument("--tokens", type=int, help="tokens the stage's agents used, when the tool reports them (effort figure)")
    s = sub.add_parser("dedupe")
    s.add_argument("--run", required=True)
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("textify")
    s.add_argument("--run", required=True)
    s.add_argument("--force", action="store_true")
    s.add_argument("--ocr-lang", default="eng")
    for name in ("evidence", "compare", "assemble", "report"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--run", required=True)
    s.add_argument("--share", type=float, default=0.10)
    s.add_argument("--min", type=int, default=5)
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("queue")
    s.add_argument("--days", type=int, default=STALE_DAYS)
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("frame")
    s.add_argument("--due", action="store_true")
    s.add_argument("--report", action="store_true")
    s.add_argument("--days", type=int)
    s.add_argument("--add")
    s.add_argument("--name")
    s.add_argument("--level")
    s.add_argument("--region")
    s.add_argument("--parent")
    s = sub.add_parser("hosts", help="the curated list of official sites")
    s.add_argument("--code")
    s.add_argument("--pending", action="store_true", help="proposed entries and unreviewed seeds")
    s.add_argument("--add", metavar="HOST")
    s.add_argument("--status")
    s.add_argument("--by")
    s.add_argument("--operator")
    s.add_argument("--kind")
    s.add_argument("--evidence-url")
    s.add_argument("--quote")
    s.add_argument("--note")
    s.add_argument("--confirm-gov", action="store_true", help="confirm the seeds on government domains (with --by)")
    s.add_argument("--batches", metavar="RUN", help="group the pending hosts, with RUN's host findings, into batch questions")
    s.add_argument("--size", type=int, help="hosts per batch (15)")
    s = sub.add_parser("questions", help="open questions for humans, as GitHub issues")
    s.add_argument("--sync", action="store_true", help="open issues for new questions and close settled ones")
    s.add_argument("--apply", action="store_true", help="apply maintainers' decisions from the issues")
    s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("intake", help="suggestions and provided documents from GitHub issues")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--triage", action="store_true", help="list undecided issues with warning signs; changes nothing")
    s = sub.add_parser("leads", help="list the leads, add one by hand, or drop a queued one")
    s.add_argument("--add", action="store_true", help="add a lead (a new instrument, or news with --record)")
    s.add_argument("--lead", help="the instrument's title, as found")
    s.add_argument("--cell", help="frame cell CODE/type, e.g. US-FL/legislature")
    s.add_argument("--code", help="jurisdiction code; the cell follows from --issued-by")
    s.add_argument("--issued-by", help="legislature, government, ministry, AI regulator, supervisory, election, "
                                       "intergovernmental")
    s.add_argument("--record", help="an existing record the lead is news about; queues a refresh instead")
    s.add_argument("--url", help="the official page, if known")
    s.add_argument("--seen-in", help="where the instrument was seen (tracker, news, law-firm note)")
    s.add_argument("--why", help="why it belongs in the register; with --drop, why the lead is dropped")
    s.add_argument("--by", help="who adds or drops the lead")
    s.add_argument("--drop", metavar="ID", help="drop a queued lead (kept with state dropped)")
    s.add_argument("--provided", metavar="FILE", help="a document a person downloaded from --url because the site "
                                                     "blocks automated downloads; stored with the lead")
    s.add_argument("--attach", metavar="ID", help="store --provided FILE with this queued lead")
    s.add_argument("--confirmed-by", help="with --provided: the maintainer who checked the file against the official site")
    s.add_argument("--issue", type=int, help="with --provided: the GitHub issue it came from")
    s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("log-human")
    s.add_argument("--run")
    s.add_argument("--id", required=True)
    s.add_argument("--result", required=True)
    s.add_argument("--note", default="")
    s.add_argument("--by")
    s = sub.add_parser("log-scope")
    s.add_argument("--run")
    s.add_argument("--id", required=True)
    s.add_argument("--decision", required=True, choices=["in", "out", "kept with a scope note"])
    s.add_argument("--note", required=True)
    s.add_argument("--by")
    args = ap.parse_args(argv)
    cmds = {"new": cmd_new, "menu": cmd_menu, "board": cmd_board, "status": cmd_status, "stage": cmd_stage, "dedupe": cmd_dedupe, "textify": cmd_textify,
            "evidence": cmd_evidence, "sample": cmd_sample, "compare": cmd_compare, "queue": cmd_queue,
            "assemble": cmd_assemble, "report": cmd_report, "frame": cmd_frame, "log-human": cmd_log_human,
            "log-scope": cmd_log_scope, "hosts": cmd_hosts, "questions": cmd_questions, "intake": cmd_intake,
            "leads": cmd_leads}
    if not args.cmd:
        ap.print_help()
        return 2
    return cmds[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
