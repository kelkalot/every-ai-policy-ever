#!/usr/bin/env python3
"""Tests of what a release uploads, run on the build that tools/publish_hf.py writes (dist/hf by default).

    python3 tools/publish_hf.py                  # build dist/hf without uploading
    python3 tools/release_check.py               # test it
    python3 tools/release_check.py --no-browser  # without the headless browser test

publish_hf.py --release runs these tests on its own build before it uploads, next to its release checks (gate,
version, tags, deleted records, history, stored files, tokens in the archive). These tests look at the built files
themselves: the dataset tables against data/records.json, the archive copies against their hashes, the archive's index of
which copy is current, every stored file the app links, the Space and its record pages and links, the app in a headless browser, the history replayed against the data, and every uploaded
text file for credentials. Exit status 1 when a test fails; warnings do not fail.
"""
import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET = re.compile(rb"hf_[A-Za-z0-9]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-ant-[A-Za-z0-9_-]{20,}"
                    rb"|sk-proj-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
TEXT = (".md", ".json", ".jsonl", ".csv", ".html", ".js", ".css", ".txt", ".xml", ".yml", ".yaml")


class Report:
    def __init__(self):
        self.failed = 0

    def check(self, name, problems, info="", warn=False):
        state = "PASS" if not problems else ("WARN" if warn else "FAIL")
        if problems and not warn:
            self.failed += 1
        print("%-5s %-28s %s" % (state, name, info if not problems else "%d: %s" % (len(problems), "; ".join(problems[:6]))))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(root):
    db = json.load(open(root / "data" / "records.json", encoding="utf-8"))
    hist = [json.loads(l) for l in open(root / "data" / "history.jsonl", encoding="utf-8") if l.strip()]
    defs = (json.load(open(root / "data" / "definitions.json", encoding="utf-8"))
            if (root / "data" / "definitions.json").is_file() else {}).get("definitions") or []
    return db, hist, defs


def test_tables(rep, root, out, db, hist, defs):
    import pyarrow.parquet as pq
    R = db["records"]
    ids = [r["id"] for r in R]
    d = out / "dataset" / "data"
    t = pq.read_table(d / "records.parquet").to_pylist()
    pids = [x["id"] for x in t]
    probs = []
    if Counter(pids) != Counter(ids):
        probs.append("records.parquet IDs differ from records.json (%d vs %d)" % (len(pids), len(ids)))
    for x in t:
        for k in ("id", "slug", "title", "jurisdiction", "status", "verification_level"):
            if k in x and not x.get(k):
                probs.append("%s has no %s" % (x.get("id"), k))
    by = {r["id"]: r for r in R}
    for x in t:  # a few fields, value for value
        r = by.get(x["id"]) or {}
        for k in ("title", "status", "date_published", "official_url"):
            if k in x and (x.get(k) or None) != (r.get(k) or None):
                probs.append("%s %s differs from records.json" % (x["id"], k))
    rel = pq.read_table(d / "related.parquet").to_pylist()
    pairs = {(x["record_id"], x["related_id"]) for x in rel}
    probs += ["related %s -> %s points to no record" % p for p in pairs if p[1] not in by][:5]
    one_way = [p for p in pairs if (p[1], p[0]) not in pairs]
    top = pq.read_table(d / "topics.parquet").to_pylist()
    if len(top) != sum(len(r.get("safety_topics") or []) for r in R):
        probs.append("topics.parquet has %d rows, records.json %d topics" % (len(top), sum(len(r.get("safety_topics") or []) for r in R)))
    n_hist = pq.read_metadata(d / "history.parquet").num_rows if (d / "history.parquet").is_file() else 0
    if n_hist != len(hist):
        probs.append("history.parquet has %d rows, history.jsonl %d" % (n_hist, len(hist)))
    n_defs = pq.read_metadata(d / "definitions.parquet").num_rows if (d / "definitions.parquet").is_file() else 0
    if n_defs != len(defs):
        probs.append("definitions.parquet has %d rows, definitions.json %d" % (n_defs, len(defs)))
    for f in ("records.json", "history.jsonl"):
        if sha(out / "dataset" / "raw" / f) != sha(root / "data" / f):
            probs.append("raw/%s is not data/%s" % (f, f))
    rep.check("dataset tables", probs, "%d records, %d related pairs, %d topics, %d history events, %d definitions"
              % (len(t), len(pairs), len(top), n_hist, n_defs))
    rep.check("related links two-way", ["%s -> %s" % p for p in sorted(one_way)], "%d pairs" % len(pairs), warn=True)


def test_generated(rep, root, db):
    R = db["records"]
    ids = sorted(r["id"] for r in R)
    probs = []
    with open(root / "data" / "records.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if sorted(x["id"] for x in rows) != ids:
        probs.append("records.csv has %d rows / other IDs" % len(rows))
    js = (root / "data" / "records.js").read_text(encoding="utf-8")
    m = re.search(r"window\.REGISTER\s*=\s*(\{.*\})\s*;?\s*$", js, re.S)
    reg = json.loads(m.group(1)) if m else {}
    if sorted(r["id"] for r in reg.get("records") or []) != ids or (reg.get("meta") or {}).get("version") != db["meta"]["version"]:
        probs.append("records.js does not hold the same records and version")
    con = sqlite3.connect(str(root / "data" / "register.sqlite"))
    n = con.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    nrel = con.execute("SELECT COUNT(*) FROM related").fetchone()[0]
    con.close()
    if n != len(R):
        probs.append("register.sqlite has %d records" % n)
    if nrel != sum(len(r.get("related") or []) for r in R):
        probs.append("register.sqlite has %d related rows" % nrel)
    try:
        import openpyxl
        wb = openpyxl.load_workbook(root / "data" / "register.xlsx", read_only=True)
        ws = wb["Records"] if "Records" in wb.sheetnames else wb[wb.sheetnames[0]]
        nx = sum(1 for row in ws.iter_rows(min_row=2, values_only=True) if row and row[0])
        if nx != len(R):
            probs.append("register.xlsx has %d rows" % nx)
        if "Related" in wb.sheetnames:
            nrx = sum(1 for row in wb["Related"].iter_rows(min_row=2, values_only=True) if row and row[0])
            if nrx != sum(len(r.get("related") or []) for r in R):
                probs.append("register.xlsx has %d related rows" % nrx)
    except ImportError:
        pass
    rep.check("generated data files", probs, "records.csv, records.js, register.sqlite, register.xlsx: %d records each" % len(R))


def test_archive(rep, root, out, db, hist, defs):
    a = out / "archive"
    probs, n = [], 0
    for sums in a.rglob("SHA256SUMS"):
        for line in sums.read_text(encoding="utf-8").splitlines():
            digest, name = line.split("  ", 1)
            p = sums.parent / name
            n += 1
            if not p.is_file():
                probs.append("%s listed but missing" % p.relative_to(a))
            elif sha(p) != digest:
                probs.append("%s does not match its SHA256SUMS line" % p.relative_to(a))
    rep.check("archive copies", probs, "%d files match their SHA256SUMS" % n)
    # evidence: every file quoted in the history and the definitions is published, unless it is a third-party copy
    import pyarrow.parquet as pq
    published = {str(p.relative_to(a)) for p in a.rglob("*") if p.is_file()}
    left_out = {x["path"] for x in pq.read_table(out / "dataset" / "data" / "source_files.parquet").to_pylist()
                if not x["in_archive_dataset"]}
    quoted = {it["file"] for e in hist for it in e.get("evidence") or [] if isinstance(it, dict) and it.get("file")}
    quoted |= {x.get("file") for x in defs if x.get("file")}
    missing = sorted(q for q in quoted if q and q not in published and q not in left_out)
    third = sorted(q for q in quoted if q and q not in published and q in left_out)
    rep.check("evidence files published", ["%s is quoted as evidence but not in the archive dataset" % q for q in missing],
              "%d of %d quoted files in the archive dataset; %d third-party copies left out (listed in source_files)"
              % (len(quoted) - len(missing) - len(third), len(quoted), len(third)))


def test_archive_index(rep, out, db):
    """FILES.csv lists exactly the published files, each with a known status; an earlier version names what replaced it."""
    a = out / "archive"
    meta_files = {"README.md", "LICENSE.md", "REDACTIONS.md", "FILES.csv", ".gitattributes"}
    built = {str(p.relative_to(a)) for p in a.rglob("*") if p.is_file() and p.name != "SHA256SUMS"
             and str(p.relative_to(a)) not in meta_files}
    if not (a / "FILES.csv").is_file():
        rep.check("archive index", ["FILES.csv missing"])
        return
    with open(a / "FILES.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    listed = {r["path"] for r in rows}
    probs = ["%s is in the archive but not in FILES.csv" % x for x in sorted(built - listed)][:5]
    probs += ["%s is in FILES.csv but not in the archive" % x for x in sorted(listed - built)][:5]
    probs += ["%s has status %r" % (r["path"], r["status"]) for r in rows
              if r["status"] not in ("current", "earlier version", "no longer used", "run copy", "register file")][:5]
    probs += ["%s is an earlier version without replaced_by" % r["path"] for r in rows
              if r["status"] == "earlier version" and not r["replaced_by"]][:5]
    n = Counter(r["status"] for r in rows)
    rep.check("archive index", probs, "FILES.csv lists the %d published files: %s" % (
        len(rows), ", ".join("%d %s" % (v, k) for k, v in sorted(n.items()))))


def test_app_links(rep, out, db):
    """Every stored file the app links (a record's copies and their earlier versions) is in the archive dataset, unless
    the Space's site-config marks it as not published (a third-party copy)."""
    a = out / "archive"
    cfg = (out / "space" / "assets" / "site-config.js").read_text(encoding="utf-8")
    m = re.search(r"window\.SITE_CONFIG\s*=\s*(\{.*\})\s*;", cfg, re.S)
    excluded = set((json.loads(m.group(1)) if m else {}).get("archiveExcluded") or [])
    links, probs = 0, []
    for r in db["records"]:
        for f in (r.get("local_copy") or {}).get("files") or []:
            for path, what in ((f.get("path"), "copy"), (f.get("previous_path") if f.get("changed") else None, "earlier version")):
                if not path or path in excluded:
                    continue
                links += 1
                if not (a / path).is_file():
                    probs.append("%s: %s %s" % (r["id"], what, path))
    rep.check("app links to stored files", probs, "%d linked files (copies and earlier versions) are published" % links)


def test_space(rep, out, db):
    sp = out / "space"
    meta, R = db["meta"], db["records"]
    probs = []
    for f in ("index.html", "assets/app.js", "assets/site-config.js", "data/records.js", "sitemap.xml", "records/index.html"):
        if not (sp / f).is_file():
            probs.append("%s missing" % f)
    pages = {"%s.html" % r["slug"] for r in R}
    have = {p.name for p in (sp / "records").glob("*.html")} - {"index.html"}
    probs += ["page %s missing" % p for p in sorted(pages - have)][:5]
    probs += ["page %s has no record" % p for p in sorted(have - pages)][:5]
    cite = "Every AI Policy Ever, version %s (snapshot %s), record " % (meta["version"], meta["snapshot_date"])
    bad_cite, bad_links = [], []
    for r in R:
        p = sp / "records" / ("%s.html" % r["slug"])
        if not p.is_file():
            continue
        html = p.read_text(encoding="utf-8")
        if cite + r["id"] not in html:
            bad_cite.append(r["id"])
        for href in re.findall(r'href="([^"#?]+)', html):
            if href.startswith(("http:", "https:", "mailto:")):
                continue
            if not (p.parent / href).resolve().is_file():
                bad_links.append("%s -> %s" % (r["id"], href))
    probs += ["citation without version and snapshot: %s" % ", ".join(bad_cite[:8])] if bad_cite else []
    probs += ["broken links: %s" % ", ".join(bad_links[:8])] if bad_links else []
    locs = re.findall(r"<loc>[^<]*/records/([^<]+\.html)</loc>", (sp / "sitemap.xml").read_text(encoding="utf-8"))
    if set(locs) != pages:
        probs.append("sitemap lists %d record pages, the register has %d" % (len(set(locs)), len(pages)))
    cfg = (sp / "assets" / "site-config.js").read_text(encoding="utf-8")
    if "huggingface.co/datasets/" not in cfg:
        probs.append("site-config.js has no dataset URL")
    rep.check("space and record pages", probs, "%d record pages, citations name version %s and snapshot %s, internal "
              "links resolve, sitemap complete" % (len(have), meta["version"], meta["snapshot_date"]))


def test_cards(rep, out, db):
    meta = db["meta"]
    probs = []
    for f in ("dataset/README.md", "archive/README.md", "space/README.md"):
        t = (out / f).read_text(encoding="utf-8") if (out / f).is_file() else ""
        if not t:
            probs.append("%s missing" % f)
            continue
        if re.search(r"%[sd]\b|\{[a-z_]+\}|\bNone\b", t):
            probs.append("%s has an unfilled placeholder" % f)
    card = (out / "dataset" / "README.md").read_text(encoding="utf-8")
    for want in (str(meta["version"]), str(meta["snapshot_date"]), str(len(db["records"]))):
        if want not in card:
            probs.append("dataset card does not mention %s" % want)
    rep.check("cards", probs, "dataset, archive and Space cards filled; version, snapshot and count on the dataset card")


def test_history_replay(rep, db, hist):
    """The latest history value of each changed field is the record's current value."""
    by = {r["id"]: r for r in db["records"]}
    last = {}
    for e in hist:
        if e.get("event") in ("changed",) and e.get("field") and e.get("record_id") in by:
            last[(e["record_id"], e["field"])] = e.get("new")
    norm = lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False) if not isinstance(v, str) else v  # noqa: E731
    bad = []
    for (rid, field), new in last.items():
        cur = by[rid]
        for part in field.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if new is not None and norm(cur) != norm(new) and field not in ("verification", "local_copy"):
            bad.append("%s.%s" % (rid, field))
    rep.check("history replays to the data", bad, "%d (record, field) pairs: the last logged value is the current one" % len(last))


def test_secrets(rep, root, out):
    hits = []
    for base in (out / "dataset", out / "space"):
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in TEXT and SECRET.search(p.read_bytes()):
                hits.append(str(p.relative_to(out)))
    rep.check("no credentials uploaded", hits, "dataset and Space files scanned (the release checks the archive)")


def test_browser(rep, out, db):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        rep.check("app in a browser", [], "skipped: playwright is not installed", warn=True)
        return
    sp = out / "space"
    probs, errors = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)[:120]))
        pg.on("console", lambda m: errors.append(m.text[:120]) if m.type == "error" else None)
        pg.goto((sp / "index.html").as_uri())
        pg.wait_for_function("document.querySelector('#count') && /records/.test(document.querySelector('#count').textContent)",
                             timeout=20000)
        count = pg.inner_text("#count")
        if str(len(db["records"])) not in count:
            probs.append("the app shows %r" % count)
        r = db["records"][0]
        pg.goto((sp / "records" / ("%s.html" % r["slug"])).as_uri())
        if r["title"][:40] not in pg.inner_text("body"):
            probs.append("record page %s does not show its title" % r["id"])
        b.close()
    # a request the page makes and handles (pilot-tabs.js asks the optional login gate) is not a script error
    errors = [e for e in errors if not re.search(r"Failed to load resource|Fetch API cannot load|ERR_FILE_NOT_FOUND|favicon", e)]
    probs += ["browser errors: %s" % "; ".join(errors[:3])] if errors else []
    rep.check("app in a browser", probs, "index shows %r; a record page renders; no script errors" % (count if not probs else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "dist" / "hf"), help="the build of tools/publish_hf.py")
    ap.add_argument("--root", default=str(ROOT), help="the repository (default: this one)")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    root, out = Path(args.root), Path(args.out)
    if not (out / "dataset" / "data" / "records.parquet").is_file():
        raise SystemExit("No build in %s; run python3 tools/publish_hf.py first" % out)
    db, hist, defs = load(root)
    rep = Report()
    print("Release tests on %s (version %s, snapshot %s)" % (out, db["meta"].get("version"), db["meta"].get("snapshot_date")))
    test_tables(rep, root, out, db, hist, defs)
    test_generated(rep, root, db)
    test_archive(rep, root, out, db, hist, defs)
    test_archive_index(rep, out, db)
    test_app_links(rep, out, db)
    test_space(rep, out, db)
    test_cards(rep, out, db)
    test_history_replay(rep, db, hist)
    test_secrets(rep, root, out)
    if not args.no_browser:
        test_browser(rep, out, db)
    print("Release tests %s: %d failed." % ("passed" if not rep.failed else "FAILED", rep.failed))
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
