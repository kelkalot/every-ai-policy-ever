#!/usr/bin/env python3
"""Regenerate the derived data files from data/records.json.

    python3 tools/build.py

Writes:
  data/records.js       the data the web app loads (works from file:// too)
  data/records.csv      one row per record, for spreadsheets
  data/register.sqlite  a relational copy for SQL queries
  data/register.xlsx    an Excel workbook (only when the openpyxl package is installed)
  records/<slug>.html   one static, no-JavaScript page per record, so search engines can index every
                        instrument without running the app (links back to the interactive register)
  sitemap.xml           the site and every record page, for search engines
  HISTORY.md            the change history from data/history.jsonl, newest first, for readers
  README.md             only the numbers between <!--n:key--> and <!--/n--> markers and the BibTeX block
                        between <!-- build:bibtex --> and <!-- /build:bibtex -->, so they follow the data

data/records.json is the single source of truth. Edit it (or let
tools/archive.py update it), then run this script. It first runs the checks in
tools/validate.py and stops if there are errors (unknown vocabulary values,
malformed dates, dangling related IDs, ...), so a bad edit never reaches the app.

Standard library only. Python 3.8+.
"""
import csv
import html as _html
import json
import re
import sqlite3
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import history  # noqa: E402  (same folder)
import validate  # noqa: E402  (same folder)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
NAME = "Every AI Policy Ever"
AUTHORS = [("Riegler", "Michael"), ("Gautam", "Sushant")]
DATASET_URL = "https://huggingface.co/datasets/kelkalot/every-ai-policy-ever"
ARCHIVE_URL = "https://huggingface.co/datasets/kelkalot/every-ai-policy-ever-archive"
REPO_URL = "https://github.com/kelkalot/every-ai-policy-ever"
# Where the web app is published; the generated pages and sitemap point here so crawlers
# get absolute URLs even when the folder is served from another host.
SPACE_URL = "https://kelkalot-every-ai-policy-ever.static.hf.space"

LOCAL_STATUSES = [
    "archived",            # official source saved, no warnings
    "archived-review",     # saved, but the content needs a human look (bot check, JS page, title mismatch)
    "partial",             # official source failed; only a secondary source was saved
    "failed",              # nothing could be saved
    "no-url",              # the record has no official URL
    "not-attempted",       # the archiver has not run for this record yet
]

CSV_COLS = [
    "id", "title", "original_title", "short_title", "jurisdiction", "country", "jurisdiction_level", "region",
    "issuing_body", "instrument_type", "legal_force", "status", "date_published", "date_in_force",
    "date_last_updated", "official_identifier", "official_url", "secondary_url", "language", "english_version",
    "english_version_url", "english_version_by", "summary",
    "safety_topics", "related_ids", "notes", "scope_note", "open_questions", "verification_level", "verified_on", "verification_method",
    "verification_note", "second_check", "local_status", "local_flag", "local_last_attempt", "local_files",
    "local_sha256",
]


def load(root=ROOT):
    with open(root / "data" / "records.json", encoding="utf-8") as f:
        return json.load(f)


def default_local_copy(rec):
    if not rec.get("official_url") and not rec.get("secondary_url"):
        return {"status": "no-url", "flag": "No official URL is recorded, so nothing can be archived.",
                "last_attempt": None, "files": [], "attempts": []}
    return {"status": "not-attempted", "flag": "The archiver has not been run for this record yet.",
            "last_attempt": None, "files": [], "attempts": []}


def normalise(db):
    for r in db["records"]:
        lc = r.get("local_copy")
        if not lc or lc.get("status") not in LOCAL_STATUSES:
            r["local_copy"] = default_local_copy(r)
        elif lc.get("status") == "not-attempted" and not r.get("official_url") and not r.get("secondary_url"):
            r["local_copy"] = default_local_copy(r)
    return db


_QUESTIONS = {}


def open_questions(root=ROOT):
    """record ID -> its open questions from pipeline/questions.json: [{"issue", "url", "title"}]."""
    key = str(root)
    if key not in _QUESTIONS:
        out = {}
        try:
            reg = json.loads((root / "pipeline" / "questions.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            reg = {}
        for q in reg.get("questions") or []:
            if q.get("state") == "open" and q.get("kind") == "record":
                out.setdefault(q.get("subject"), []).append(
                    {"issue": q.get("issue"), "url": q.get("url"), "run_id": q.get("run_id"),
                     "why": (q.get("why") or "")[:300]})
        _QUESTIONS[key] = out
    return _QUESTIONS[key]


def flat(r):
    v = r.get("verification") or {}
    ev = r.get("english_version") or {}
    lc = r.get("local_copy") or {}
    files = lc.get("files") or []
    return {
        "id": r["id"], "title": r.get("title"), "original_title": r.get("original_title"),
        "short_title": r.get("short_title"), "jurisdiction": r.get("jurisdiction"), "country": r.get("country"),
        "jurisdiction_level": r.get("jurisdiction_level"), "region": r.get("region"),
        "issuing_body": r.get("issuing_body"), "instrument_type": r.get("instrument_type"),
        "legal_force": r.get("legal_force"), "status": r.get("status"), "date_published": r.get("date_published"),
        "date_in_force": r.get("date_in_force"), "date_last_updated": r.get("date_last_updated"),
        "official_identifier": r.get("official_identifier"), "official_url": r.get("official_url"),
        "secondary_url": r.get("secondary_url"), "language": r.get("language"),
        "english_version": ev.get("kind"), "english_version_url": ev.get("url"), "english_version_by": ev.get("by"),
        "summary": r.get("summary"),
        "safety_topics": "; ".join(r.get("safety_topics") or []),
        "related_ids": "; ".join(x.get("id") for x in (r.get("related") or []) if x.get("id")),
        "notes": r.get("notes"), "scope_note": r.get("scope_note"),
        "open_questions": "; ".join(q["url"] or "open question (no issue yet)" for q in open_questions().get(r["id"], [])) or None,
        "verification_level": v.get("level"), "verified_on": v.get("verified_on"),
        "verification_method": v.get("method"), "verification_note": v.get("note"),
        "second_check": v.get("second_check"), "local_status": lc.get("status"),
        "local_flag": " ".join(x for x in (lc.get("flag"), lc.get("integrity_flag")) if x) or None,
        "local_last_attempt": lc.get("last_attempt"),
        "local_files": "; ".join(f.get("path", "") for f in files),
        "local_sha256": "; ".join(f.get("sha256", "") for f in files),
    }


def history_for_app(root=ROOT):
    """The history per record for the app, with evidence cut down to the first quote."""
    out = {}
    for e in history.load(root):
        ev = e.get("evidence") or []
        first = ev[0] if ev and isinstance(ev[0], dict) else {}
        out.setdefault(e.get("record_id"), []).append({
            "date": e.get("date"), "run_id": e.get("run_id"), "event": e.get("event"), "field": e.get("field"),
            "old": e.get("old"), "new": e.get("new"), "reason": e.get("reason"), "tool": e.get("tool"),
            "model": e.get("model"), "evidence": len(ev),
            "quote": (first.get("quote") or "")[:240] or None, "file": first.get("file")})
    return out


def definitions_table(db, root=ROOT):
    """The definitions of data/definitions.json, each with source_changed: true when its file and SHA-256 are no
    longer a current stored file of its record (a compare run has to quote it again; tools/definitions.py queue)."""
    src = root / "data" / "definitions.json"
    if not src.is_file():
        return []
    cur = {}
    for r in db["records"]:
        for f in (r.get("local_copy") or {}).get("files") or []:
            if f.get("path") and not f.get("stale"):  # from records.json only, so that a clone without archive/ builds the same
                cur[(r["id"], f["path"])] = f.get("sha256")
    rows = json.loads(src.read_text(encoding="utf-8")).get("definitions") or []
    return [dict(d, source_changed=cur.get((d["record_id"], d.get("file"))) != d.get("sha256")) for d in rows]


def write_js(db, root=ROOT):
    hist = history_for_app(root)
    _QUESTIONS.pop(str(root), None)
    payload = dict(db, history=hist) if hist else dict(db)
    payload["questions"] = open_questions(root)
    defs = definitions_table(db, root)
    if defs:  # the definitions layer of the crosswalk (issue #70): checked definitions only
        keep = ("id", "record_id", "term", "term_group", "definition", "english", "english_by", "language", "locator",
                "text_layer", "source_changed")
        payload["definitions"] = [{k: d.get(k) for k in keep if d.get(k) not in (None, False)} for d in defs]
    payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    text = ("/* Generated by tools/build.py from data/records.json. Do not edit by hand. */\n"
            "window.REGISTER = " + payload + ";\n")
    (root / "data" / "records.js").write_text(text, encoding="utf-8")


def write_csv(db, root=ROOT):
    with open(root / "data" / "records.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        for r in db["records"]:
            w.writerow(flat(r))


# ---------- static record pages and sitemap ----------
#
# One page per record, with no JavaScript: search engines that do not render the app
# can still find and read every instrument. The interactive register stays the main
# interface; these pages link back to it.


def _esc(s):
    return _html.escape("" if s is None else str(s), quote=True)


def _when(s):
    return (s or "").replace("T", " ").replace("Z", " UTC").strip()


def _slugmap(db):
    """record ID -> page file name; a collision keeps the record ID as a suffix."""
    out = {}
    for r in db["records"]:
        s = (r.get("slug") or r["id"].lower()).replace("/", "-")
        if s in out.values():
            s = "%s-%s" % (s, r["id"].lower())
        out[r["id"]] = s
    return out


def citation_text(r, meta):
    """The same citation the app's copy button offers."""
    v = r.get("verification") or {}
    f = next((x for x in (r.get("local_copy") or {}).get("files") or [] if not x.get("stale")), None)
    local = "Local copy %s retrieved %s, SHA-256 %s." % (f["path"], _when(f.get("retrieved_at")), f.get("sha256")) if f else ""
    parts = [
        (r.get("issuing_body") or "") + ".",
        (r.get("title") or "") + ((" [%s]" % r["official_identifier"]) if r.get("official_identifier") else "") + ".",
        (r.get("date_published") or "n.d.") + ".",
        r["official_url"] + "." if r.get("official_url") else "",
        "Status: %s; verified %s (level %s)." % (r.get("status"), v.get("verified_on"), v.get("level")),
        local,
        "Every AI Policy Ever, version %s (snapshot %s), record %s." % (meta.get("version"), meta.get("snapshot_date"), r["id"]),
    ]
    return " ".join(p for p in parts if p)


RECORD_CSS = """
:root{--bg:#f2f4f7;--surface:#ffffff;--ink:#111924;--ink-2:#455263;--ink-3:#6a7686;--line:#d5dce5;--accent:#2c43b0;--accent-ink:#fff;--accent-soft:#e3e7fa;--ok:#157a3a;--ok-soft:#e1f3e6;--warn:#8f5a00;--warn-soft:#fbefd6;--bad:#b0222a;--bad-soft:#fbe4e4;--gone:#5f6875;--gone-soft:#e7eaee}
@media (prefers-color-scheme: dark){:root{--bg:#0e131a;--surface:#151c25;--ink:#e6ebf1;--ink-2:#a9b4c2;--ink-3:#8390a1;--line:#29343f;--accent:#8e9dff;--accent-ink:#0e131a;--accent-soft:#222b52;--ok:#63cf88;--ok-soft:#15301f;--warn:#e5b45b;--warn-soft:#332714;--bad:#ff8b8b;--bad-soft:#3a1b1d;--gone:#9aa4b1;--gone-soft:#242c36}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--accent)}a:hover{text-decoration:underline}
.wrap{max-width:880px;margin:0 auto;padding:20px 20px 56px}
.crumb{font-size:13px;color:var(--ink-3)}.crumb a{color:var(--ink-2)}
.kicker{font-size:13px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--ink-2);margin:16px 0 6px}
h1{font-size:33px;line-height:1.18;margin:0 0 8px}h2{font-size:19px;margin:0 0 10px;padding-top:22px;border-top:1px solid var(--line)}
section{margin-top:26px}
.orig{color:var(--ink-2);font-size:17px;margin:0 0 10px}
.idline{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;color:var(--ink-3)}
dl.facts{display:grid;grid-template-columns:190px 1fr;gap:5px 16px;margin:18px 0 0;padding:14px 16px;background:var(--surface);border:1px solid var(--line);border-radius:6px}
dl.facts dt{color:var(--ink-3);font-size:14px}dl.facts dd{margin:0;overflow-wrap:anywhere}
.tag{display:inline-block;background:var(--accent-soft);color:var(--accent);border-radius:999px;padding:2px 10px;font-size:13px;margin:0 6px 6px 0}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:13px;font-weight:600;margin-right:8px}
.p-inforce{background:var(--ok-soft);color:var(--ok)}.p-published{background:var(--accent-soft);color:var(--accent)}
.p-draft{background:var(--accent-soft);color:var(--accent)}.p-gone{background:var(--gone-soft);color:var(--gone)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
.muted{color:var(--ink-3);font-size:14px}
.flag{border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:6px;padding:10px 12px;margin:8px 0;background:var(--surface)}
.flag-warn{border-left-color:var(--warn)}
.file{border:1px solid var(--line);border-radius:6px;padding:10px 12px;margin:8px 0;background:var(--surface)}
.verify{display:flex;gap:14px;align-items:baseline;background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px}
.verify .big{font-size:30px;font-weight:700;color:var(--accent)}
.verify .vm{color:var(--ink-3);font-size:13px}.verify .vn{margin-top:6px;font-size:14px;color:var(--ink-2)}
ol.hist{margin:0;padding-left:18px}ol.hist li{margin:0 0 10px}ol.hist .hd{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;color:var(--ink-3);margin-right:8px}
ol.hist .hm{display:block;color:var(--ink-3);font-size:12px;margin-top:2px}
pre.cite{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px;white-space:pre-wrap;overflow-wrap:anywhere;font:13.5px/1.5 ui-monospace,Menlo,Consolas,monospace;margin:0}
footer{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);color:var(--ink-3);font-size:13px}
"""


def _record_page(r, db, hist, questions, reverse_rel, slugmap):
    v = r.get("verification") or {}
    lc = r.get("local_copy") or {}
    ev = r.get("english_version") or {}
    meta = db.get("meta") or {}
    rid = r["id"]
    slug = slugmap[rid]
    page_url = "%s/records/%s.html" % (SPACE_URL, slug)
    title = r.get("title") or rid
    desc = r.get("summary") or "%s: official AI safety and AI regulation instruments." % NAME
    if len(desc) > 155:
        desc = desc[:152].rstrip() + "…"

    def fact(label, value):
        if not value:
            return ""
        return '    <dt>%s</dt><dd>%s</dd>\n' % (_esc(label), _esc(value))

    # --- kicker + title
    status = r.get("status") or ""
    sclass = {"In force": "p-inforce", "Partially in force": "p-inforce",
              "Published (non-binding, current)": "p-published",
              "Adopted, not yet in force": "p-published"}.get(status, "p-draft" if status == "Draft / proposed" else "p-gone")
    body = []
    body.append('  <p class="kicker"><span class="pill %s">%s</span>%s · %s</p>\n' %
                (sclass, _esc(status), _esc(r.get("legal_force") or ""), _esc(r.get("instrument_type") or "")))
    body.append("  <h1>%s</h1>\n" % _esc(title))
    if r.get("original_title"):
        body.append('  <p class="orig">%s</p>\n' % _esc(r["original_title"]))
    idline = "Record %s" % rid + ((" · %s" % r["official_identifier"]) if r.get("official_identifier") else "")
    body.append('  <p class="idline">%s</p>\n' % _esc(idline))

    facts = (fact("Issued by", r.get("issuing_body")) + fact("Jurisdiction", r.get("jurisdiction")) +
             fact("Level · region", ("%s · %s" % (r.get("jurisdiction_level"), r.get("region"))) if r.get("jurisdiction_level") else None) +
             (fact("Country", r.get("country")) if r.get("jurisdiction_level") == "Sub-national" and r.get("country") else "") +
             fact("Published / adopted", r.get("date_published")) + fact("In force", r.get("date_in_force")) +
             fact("Last updated", r.get("date_last_updated")) + fact("Language", r.get("language")) +
             fact("Official identifier", r.get("official_identifier")))
    if facts:
        body.append('  <dl class="facts">\n' + facts + "  </dl>\n")

    body.append('  <section><h2>Summary</h2><p>%s</p></section>\n' % _esc(r.get("summary") or ""))

    # language note, same rule as the app
    lang = r.get("language") or ""
    english_original = bool(re.match(r"^All 24 official EU languages", lang)) or \
        any(x.strip().lower() == "english" for x in lang.split(","))
    kind = ev.get("kind")
    if kind != "authentic" and not english_original:
        link = " <a href=\"%s\">Open it</a>." % _esc(ev["url"]) if ev.get("url") else "."
        if kind == "government translation":
            t = "English translation by %s%s The %s text is authoritative." % (_esc(ev.get("by") or "a public body"), link, _esc(lang or "original-language"))
        elif kind == "third-party translation":
            t = "English translation by %s, not by a public body%s The %s text is authoritative." % (_esc(ev.get("by") or "a third party"), link, _esc(lang or "original-language"))
        elif kind == "none found":
            t = "No English version of this instrument was found. The English title and the summary are the register's own, written from the sources below; for the exact wording use the %s text." % _esc(lang or "original-language")
        else:
            t = "No English version is recorded for this record yet. The English title may be the register's own rendering, and the summary was written from the sources below; for the exact wording use the %s text." % _esc(lang or "original-language")
        body.append('  <section><h2>Language</h2><p>%s</p></section>\n' % t)

    if r.get("safety_topics"):
        tags = "".join('<span class="tag">%s</span>' % _esc(t) for t in r["safety_topics"])
        body.append('  <section><h2>Safety topics</h2>%s</section>\n' % tags)

    if r.get("scope_note"):
        body.append('  <section><h2>Scope</h2><p><span class="pill p-published">Borderline scope</span> %s</p></section>\n' % _esc(r["scope_note"]))

    qs = questions.get(rid) or []
    if qs:
        ps = "".join("<p>%s <a href=\"%s\">Issue #%s</a></p>" % (_esc(q.get("why") or ""), _esc(q.get("url") or REPO_URL + "/issues"), _esc(q.get("issue") or ""))
                     for q in qs if q.get("url"))
        body.append('  <section><h2>Open question</h2>%s<p class="muted">The record shows its last checked values until a maintainer decides; the decision is recorded in its history.</p></section>\n' % ps)

    if r.get("notes"):
        body.append('  <section><h2>Status notes</h2><p>%s</p></section>\n' % _esc(r["notes"]))

    srcs = ""
    if r.get("official_url"):
        srcs += '<p><a href="%s" rel="noopener">Open the official source</a> <span class="mono">%s</span></p>\n' % (_esc(r["official_url"]), _esc(r["official_url"]))
    if r.get("secondary_url"):
        srcs += '<p>Secondary source: <a href="%s" rel="noopener">%s</a></p>\n' % (_esc(r["secondary_url"]), _esc(r["secondary_url"]))
    if not srcs:
        srcs = '<p class="muted">No official URL could be confirmed for this record.</p>\n'
    body.append('  <section><h2>Sources</h2>%s</section>\n' % srcs)

    # local copy
    LC = {"archived": "Archived", "archived-review": "Archived, needs review", "partial": "Partial (secondary source only)",
          "failed": "Download failed", "no-url": "No URL to archive", "not-attempted": "Not archived yet"}
    lch = '<p><strong>%s.</strong> %s%s</p>\n' % (
        LC.get(lc.get("status"), "Local copy"), _esc(lc.get("flag") or ""),
        (" <span class=\"muted\">Last attempt %s</span>" % _when(lc.get("last_attempt"))) if lc.get("last_attempt") else "")
    lcf = ""
    for f in lc.get("files") or []:
        link = ('<a href="%s/blob/main/%s" rel="noopener">%s</a>' % (ARCHIVE_URL, _esc(f.get("path") or ""), _esc(f.get("label") or f.get("role") or "Stored file"))) \
            if f.get("in_archive_dataset") else ('<span>%s <span class="muted">(third-party copy, not published)</span></span>' % _esc(f.get("label") or f.get("role") or "Stored file"))
        warn = ""
        if f.get("warning"):
            warn += '<p class="muted">Warning: %s</p>' % _esc(f["warning"])
        if f.get("integrity") and f["integrity"] != "ok":
            warn += '<p class="muted">Integrity check: %s</p>' % _esc(f["integrity"])
        if f.get("redaction_note"):
            warn += '<p class="muted">Published copy: %s. The SHA-256 above is the original file\'s.</p>' % _esc(f["redaction_note"])
        lcf += ('<div class="file"><div>%s <span class="mono">%s</span></div>'
                '<div class="muted">Retrieved %s</div><div class="mono">SHA-256 %s</div>%s</div>\n' % (
                    link, _esc(f.get("path") or ""), _when(f.get("retrieved_at")), _esc(f.get("sha256") or ""), warn))
    if lc.get("status") != "no-url":
        body.append('  <section><h2>Local copy</h2><div class="flag">%s%s</div></section>\n' % (lch, lcf))

    # verification
    VLABEL = {"A": "The instrument's own official text, or an official register, was stored and confirms the title, date "
                   "and status.",
              "B": "Another official source, such as an announcement by the issuer, confirms the title, date and status.",
              "C": "Not confirmed on an official page; the record rests on secondary sources. Check it before citing."}
    sc = v.get("second_check")
    body.append('  <section><h2>Verification</h2><div class="verify"><span class="big">%s</span>'
                '<div><div>%s <span class="vm">checked %s · %s</span></div>'
                '<div class="vn">%s</div>%s</div></div></section>\n' % (
                    _esc(v.get("level") or "?"), _esc(VLABEL.get(v.get("level"), "")),
                    _esc(v.get("verified_on") or ""), _esc(v.get("method") or ""),
                    _esc(v.get("note") or ""),
                    ('<div class="vn"><strong>Second check:</strong> %s</div>' % _esc(sc)) if sc else ""))

    # history, newest first
    he = hist.get(rid) or []
    if he:
        def ht(e):
            s = lambda val: ("–" if val in (None, "") else (val if isinstance(val, str) else json.dumps(val)))[:80]
            kind = e.get("event")
            if kind == "changed":
                return "%s: %s → %s" % (e.get("field"), s(e.get("old")), s(e.get("new")))
            return {"added": "Added to the register", "re-verified": "Re-verified against its sources, no change",
                    "human-checked": "Checked by a human: %s" % s(e.get("new")),
                    "scope-decision": "Scope decision: %s" % s(e.get("new")),
                    "source-changed": "A stored source changed", "human-decision": "Maintainer decision",
                    "definition-added": "Defined term quoted: %s" % s(e.get("field")),
                    "definition-changed": "%s: %s → %s" % (e.get("field"), s(e.get("old")), s(e.get("new")))}.get(kind, kind or "")
        rows = ""
        for e in reversed(he):
            who = e.get("tool") or ""
            if e.get("model"):
                who += " (%s)" % e["model"]
            rows += ('<li><span class="hd">%s</span>%s%s'
                     '<span class="hm">%s%s</span></li>\n' % (
                         _esc(e.get("date") or ""), _esc(ht(e)),
                         (' <span class="muted">— %s</span>' % _esc(e.get("reason"))) if e.get("reason") else "",
                         _esc(e.get("run_id") or ""),
                         ((" · " + who) if who else "")))
        body.append('  <section><h2>History</h2><ol class="hist">%s</ol></section>\n' % rows)

    # related records, both directions, as links to the static pages
    fwd = [x.get("id") for x in (r.get("related") or []) if x.get("id") in slugmap and x.get("id") != rid]
    seen = set(fwd)
    rev = [x for x in (reverse_rel.get(rid) or []) if x not in seen and x in slugmap]
    if fwd or rev:
        byid = {x["id"]: x for x in db["records"]}
        rows = "".join('<p><a href="%s.html">%s</a> <span class="muted">%s · %s</span></p>\n' % (
            slugmap[i], _esc(byid[i].get("short_title") or byid[i].get("title") or i),
            _esc(byid[i].get("jurisdiction") or ""), _esc(byid[i].get("status") or "")) for i in fwd + rev)
        body.append('  <section><h2>Related records</h2>%s</section>\n' % rows)

    body.append('  <section><h2>Citation</h2><pre class="cite">%s</pre></section>\n' % _esc(citation_text(r, meta)))

    issue_q = urllib.parse.urlencode({"template": "suggest-instrument.yml",
                                      "title": "News or correction: %s %s" % (rid, r.get("short_title") or r.get("title") or ""),
                                      "record": rid, "url": r.get("official_url") or "",
                                      "jurisdiction": re.sub(r"-\d+$", "", rid)})
    improve = ('  <section><h2>Improve this record</h2><p>Know of an amendment, a status change or an error? '
               '<a href="%s" target="_blank" rel="noopener">Report news or an error</a> on GitHub; the form opens with this record filled in.</p></section>\n' %
               _esc(REPO_URL + "/issues/new?" + issue_q))
    body.append(improve)

    # JSON-LD
    ld = {
        "@context": "https://schema.org",
        "@type": "GovernmentDocument",
        "name": title,
        "identifier": r.get("official_identifier") or rid,
        "description": r.get("summary") or "",
        "url": page_url,
        "dateCreated": r.get("date_published"),
        "dateModified": r.get("date_last_updated") or v.get("verified_on"),
        "inLanguage": r.get("language"),
        "isAccessibleForFree": True,
        "about": r.get("safety_topics") or [],
        "creator": {"@type": "Organization", "name": r.get("issuing_body") or NAME},
    }
    if r.get("official_url"):
        ld["sourceUrl"] = r["official_url"]
    ld2 = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Register", "item": SPACE_URL + "/"},
        {"@type": "ListItem", "position": 2, "name": title, "item": page_url}]}
    ld_text = json.dumps([ld, ld2], ensure_ascii=False, separators=(",", ":"))

    head = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>%s (%s) · %s</title>" % (_esc(title), _esc(rid), _esc(NAME)),
        '<meta name="description" content="%s">' % _esc(desc),
        '<link rel="canonical" href="%s">' % _esc(page_url),
        '<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">',
        '<style>%s</style>' % RECORD_CSS,
        '<meta property="og:type" content="article">',
        '<meta property="og:site_name" content="%s">' % _esc(NAME),
        '<meta property="og:title" content="%s">' % _esc("%s (%s)" % (title, rid)),
        '<meta property="og:description" content="%s">' % _esc(desc),
        '<meta property="og:url" content="%s">' % _esc(page_url),
        '<meta property="og:image" content="%s/assets/og-image.png">' % SPACE_URL,
        '<meta name="twitter:card" content="summary">',
        '<meta name="twitter:title" content="%s">' % _esc("%s (%s)" % (title, rid)),
        '<meta name="twitter:description" content="%s">' % _esc(desc),
        '<script type="application/ld+json">%s</script>' % ld_text.replace("</", "<\\/"),
        "</head>",
        '<body>',
        '<div class="wrap">',
        '  <p class="crumb"><a href="../index.html">Every AI Policy Ever</a> · <a href="../index.html#%s">open in the interactive register</a></p>\n' % _esc(rid),
    ]
    tail = [
        "  <footer>%s · version %s · snapshot %s · an AI-assisted extraction, verified %s (level %s) · "
        "<a href=\"../index.html\">the interactive register</a> · <a href=\"%s\" rel=\"noopener\">the GitHub repository</a></footer>\n" % (
            _esc(NAME), _esc(meta.get("version") or ""), _esc(meta.get("snapshot_date") or ""),
            _esc(v.get("verified_on") or ""), _esc(v.get("level") or ""), _esc(REPO_URL)),
        "</div>",
        "</body>",
        "</html>",
    ]
    return "\n".join(head) + "\n" + "\n".join(body) + "\n".join(tail) + "\n"


def _records_index(db, slugmap):
    """records/index.html: a static list of every record, so /records/ is a page, not a dead end."""
    meta = db.get("meta") or {}
    page_url = SPACE_URL + "/records/"
    recs = sorted(db["records"], key=lambda r: (r.get("date_published") or "", r["id"]), reverse=True)
    rows = "".join(
        '<p><a href="%s.html">%s</a> <span class="muted">%s · %s · %s</span></p>\n' % (
            slugmap[r["id"]], _esc(r.get("short_title") or r.get("title") or r["id"]),
            _esc(r["id"]), _esc(r.get("jurisdiction") or ""), _esc(r.get("date_published") or ""))
        for r in recs)
    return "\n".join([
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>All records · %s</title>" % _esc(NAME),
        '<meta name="description" content="All %d records in %s: official governmental and intergovernmental AI safety and AI regulation instruments, newest first."' % (len(recs), NAME),
        '<link rel="canonical" href="%s">' % _esc(page_url),
        '<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">',
        "<style>%s</style>" % RECORD_CSS,
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="%s">' % _esc(NAME),
        '<meta property="og:title" content="All records · %s">' % _esc(NAME),
        '<meta property="og:description" content="All %d records, newest first." % len(recs)',
        '<meta property="og:url" content="%s">' % _esc(page_url),
        '<meta property="og:image" content="%s/assets/og-image.png">' % SPACE_URL,
        "</head>",
        "<body>",
        '<div class="wrap">',
        '  <p class="crumb"><a href="../index.html">Every AI Policy Ever</a> · <a href="../index.html">open in the interactive register</a></p>',
        '  <h1>All records <span style="color:var(--ink-3);font-size:20px">(%d)</span></h1>\n' % len(recs),
        '  <p class="muted">Every instrument in the register, newest first. Snapshot %s · version %s. Use the <a href="../index.html">interactive register</a> to search and filter.</p>\n' % (_esc(meta.get("snapshot_date") or ""), _esc(meta.get("version") or "")),
        rows,
        '  <footer>%s · version %s · snapshot %s</footer>\n' % (_esc(NAME), _esc(meta.get("version") or ""), _esc(meta.get("snapshot_date") or "")),
        "</div>",
        "</body>",
        "</html>",
    ]) + "\n"


def write_record_pages(db, root=ROOT):
    """One static, no-JavaScript HTML page per record under records/, plus its sitemap."""
    out = root / "records"
    if out.is_dir():
        for f in out.iterdir():  # a record may change its slug; the folder is fully generated
            if f.suffix == ".html":
                f.unlink()
    hist = history_for_app(root)
    questions = open_questions(root)
    slugmap = _slugmap(db)
    ids = set(slugmap)
    reverse = {}
    for r in db["records"]:
        for x in r.get("related") or []:
            if x.get("id") in ids and x["id"] != r["id"]:
                reverse.setdefault(x["id"], []).append(r["id"])
    out.mkdir(parents=True, exist_ok=True)
    for r in db["records"]:
        (out / (slugmap[r["id"]] + ".html")).write_text(
            _record_page(r, db, hist, questions, reverse, slugmap), encoding="utf-8")
    (out / "index.html").write_text(_records_index(db, slugmap), encoding="utf-8")
    return len(db["records"])


def write_sitemap(db, root=ROOT):
    meta = db.get("meta") or {}
    lastmod = meta.get("snapshot_date") or ""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             "  <!-- Generated by tools/build.py. -->"]

    def url(line_loc):
        return "  <url><loc>%s</loc>%s</url>" % (line_loc, ("<lastmod>%s</lastmod>" % lastmod) if lastmod else "")

    lines.append(url(SPACE_URL + "/"))
    lines.append(url(SPACE_URL + "/records/"))
    byid = {r["id"]: r for r in db["records"]}
    slugmap = _slugmap(db)
    for rid in sorted(slugmap, key=lambda i: (byid[i].get("date_published") or "", i)):
        lines.append(url("%s/records/%s.html" % (SPACE_URL, slugmap[rid])))
    lines.append("</urlset>")
    (root / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_sqlite(db, root=ROOT):
    path = root / "data" / "register.sqlite"
    tmp = path.with_suffix(".sqlite.tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(str(tmp))
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE records (
      id TEXT PRIMARY KEY, slug TEXT, title TEXT, original_title TEXT, short_title TEXT,
      jurisdiction TEXT, country TEXT, jurisdiction_level TEXT, region TEXT, issuing_body TEXT,
      instrument_type TEXT, legal_force TEXT, status TEXT,
      date_published TEXT, date_in_force TEXT, date_last_updated TEXT,
      official_identifier TEXT, official_url TEXT, secondary_url TEXT, language TEXT,
      english_version TEXT, english_version_url TEXT, english_version_by TEXT,
      summary TEXT, notes TEXT, scope_note TEXT,
      verification_level TEXT, verified_on TEXT, verification_method TEXT, verification_note TEXT, second_check TEXT,
      local_status TEXT, local_flag TEXT, local_last_attempt TEXT
    );
    CREATE TABLE topics (record_id TEXT REFERENCES records(id), topic TEXT);
    CREATE TABLE related (record_id TEXT REFERENCES records(id), related_id TEXT REFERENCES records(id));
    CREATE TABLE open_questions (record_id TEXT REFERENCES records(id), issue INTEGER, url TEXT, question TEXT);
    CREATE TABLE archive_files (
      record_id TEXT REFERENCES records(id), role TEXT, path TEXT, url TEXT, final_url TEXT,
      http_status INTEGER, content_type TEXT, bytes INTEGER, sha256 TEXT, retrieved_at TEXT,
      last_checked TEXT, method TEXT, last_modified TEXT, warning TEXT, integrity TEXT
    );
    CREATE TABLE archive_attempts (
      record_id TEXT REFERENCES records(id), role TEXT, url TEXT, attempted_at TEXT,
      ok INTEGER, http_status INTEGER, error TEXT
    );
    CREATE INDEX idx_records_country ON records(country);
    CREATE INDEX idx_records_status ON records(status);
    CREATE INDEX idx_records_local ON records(local_status);
    CREATE INDEX idx_topics ON topics(topic);
    """)
    for k, v in (db.get("meta") or {}).items():
        cur.execute("INSERT INTO meta VALUES (?, ?)", (k, json.dumps(v) if isinstance(v, (dict, list)) else str(v)))
    for r in db["records"]:
        v = r.get("verification") or {}
        lc = r.get("local_copy") or {}
        ev = r.get("english_version") or {}
        cur.execute("INSERT INTO records VALUES (" + ",".join(["?"] * 34) + ")", (
            r["id"], r.get("slug"), r.get("title"), r.get("original_title"), r.get("short_title"),
            r.get("jurisdiction"), r.get("country"), r.get("jurisdiction_level"), r.get("region"),
            r.get("issuing_body"), r.get("instrument_type"), r.get("legal_force"), r.get("status"),
            r.get("date_published"), r.get("date_in_force"), r.get("date_last_updated"),
            r.get("official_identifier"), r.get("official_url"), r.get("secondary_url"), r.get("language"),
            ev.get("kind"), ev.get("url"), ev.get("by"),
            r.get("summary"), r.get("notes"), r.get("scope_note"),
            v.get("level"), v.get("verified_on"), v.get("method"), v.get("note"), v.get("second_check"),
            lc.get("status"), " ".join(x for x in (lc.get("flag"), lc.get("integrity_flag")) if x) or None,
            lc.get("last_attempt"),
        ))
        for t in r.get("safety_topics") or []:
            cur.execute("INSERT INTO topics VALUES (?, ?)", (r["id"], t))
        for q in open_questions().get(r["id"], []):
            cur.execute("INSERT INTO open_questions VALUES (?, ?, ?, ?)", (r["id"], q.get("issue"), q.get("url"), q.get("why")))
        for x in r.get("related") or []:
            if x.get("id"):
                cur.execute("INSERT INTO related VALUES (?, ?)", (r["id"], x["id"]))
        for f in lc.get("files") or []:
            cur.execute("INSERT INTO archive_files VALUES (" + ",".join(["?"] * 15) + ")", (
                r["id"], f.get("role"), f.get("path"), f.get("url"), f.get("final_url"), f.get("http_status"),
                f.get("content_type"), f.get("bytes"), f.get("sha256"), f.get("retrieved_at"),
                f.get("last_checked"), f.get("method"), f.get("last_modified"), f.get("warning"),
                f.get("integrity"),
            ))
        for a in lc.get("attempts") or []:
            cur.execute("INSERT INTO archive_attempts VALUES (?, ?, ?, ?, ?, ?, ?)", (
                r["id"], a.get("role"), a.get("url"), a.get("attempted_at"), 1 if a.get("ok") else 0,
                a.get("http_status"), a.get("error"),
            ))
    con.commit()
    con.close()
    tmp.replace(path)


def write_history_md(root=ROOT):
    """HISTORY.md: every event in data/history.jsonl, grouped by run, newest first."""
    events = history.load(root)
    if not events:
        return False
    runs = {}
    for e in events:
        runs.setdefault((e.get("date") or "", e.get("run_id") or "-"), []).append(e)
    lines = ["# Change history", "",
             "Generated by tools/build.py from data/history.jsonl. Every addition, change and re-verification of a record, "
             "and every human check and scope decision, newest first. The evidence for each event (file, SHA-256 and quote) "
             "is in data/history.jsonl; `python3 tools/history.py <ID>` shows one record.", ""]
    for (date, run_id), evs in sorted(runs.items(), key=lambda kv: kv[0], reverse=True):
        report = root / "runs" / run_id / "report.md"
        title = "## %s · %s" % (date, ("[%s](runs/%s/report.md)" % (run_id, run_id)) if report.is_file() else run_id)
        kinds = {}
        for e in evs:
            kinds[e["event"]] = kinds.get(e["event"], 0) + 1
        lines += [title, "", ", ".join("%s %d" % kv for kv in sorted(kinds.items())), ""]
        for e in evs:
            lines.append("- **%s** %s%s" % (e.get("record_id"), history.describe(e),
                                            (" — %s" % e["reason"]) if e.get("reason") else ""))
        lines.append("")
    (root / "HISTORY.md").write_text("\n".join(lines), encoding="utf-8")
    return True


def bibtex(meta, url=DATASET_URL):
    year = (meta.get("snapshot_date") or "")[:4]
    return ("@dataset{riegler_gautam_%s_every_ai_policy_ever,\n"
            "  title     = {%s: a register of official AI safety and AI regulation instruments},\n"
            "  author    = {%s},\n  year      = {%s},\n  version   = {%s},\n  publisher = {Hugging Face},\n"
            "  url       = {%s},\n  note      = {AI-assisted extraction, snapshot %s}\n}") % (
        year, NAME, " and ".join("%s, %s" % a for a in AUTHORS), year, meta.get("version"), url,
        meta.get("snapshot_date"))


def numbers(db):
    """The figures the README quotes, computed from the data."""
    R = db["records"]
    levels = Counter((r.get("verification") or {}).get("level") for r in R)
    years = [(r.get("date_published") or "")[:4] for r in R if (r.get("date_published") or "")[:4].isdigit()]
    return {"version": db["meta"].get("version"), "records": len(R), "snapshot": db["meta"].get("snapshot_date"),
            "level_A": levels["A"], "level_B": levels["B"], "level_C": levels["C"],
            "countries": len({r.get("country") for r in R if r.get("jurisdiction_level") in ("National", "Sub-national")}),
            "from_2023": sum(1 for y in years if y >= "2023"), "before_2023": sum(1 for y in years if y < "2023"),
            "first_year": min(years) if years else ""}


NUMBER = re.compile(r"<!--n:(\w+)-->.*?<!--/n-->", re.S)
BIBTEX = re.compile(r"(<!-- build:bibtex -->\n).*?(\n<!-- /build:bibtex -->)", re.S)


def write_readme(db, root=ROOT):
    """Put the current figures and citation into README.md, so the documentation does not drift from the data."""
    path = root / "README.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    n = numbers(db)

    def fill(m):
        if m.group(1) not in n:
            raise SystemExit("README.md: no figure called %r (known: %s)" % (m.group(1), ", ".join(sorted(n))))
        return "<!--n:%s-->%s<!--/n-->" % (m.group(1), n[m.group(1)])
    new = NUMBER.sub(fill, text)
    new = BIBTEX.sub(lambda m: m.group(1) + "```bibtex\n" + bibtex(db["meta"]) + "\n```" + m.group(2), new)
    if new != text:
        path.write_text(new, encoding="utf-8")


def write_definitions_csv(db, root=ROOT):
    """data/definitions.csv from data/definitions.json, the definitions layer of the crosswalk (issue #70)."""
    rows = definitions_table(db, root)
    if not rows:
        return
    cols = ["id", "record_id", "term", "term_group", "definition", "english", "english_by", "language", "locator",
            "text_layer", "source_changed", "file", "sha256", "run_id"]
    with open(root / "data" / "definitions.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(dict({k: r.get(k) for k in cols}, source_changed="yes" if r.get("source_changed") else ""))


def save(db, root=ROOT):
    """Write records.json atomically and regenerate every derived file."""
    db = normalise(db)
    db.setdefault("meta", {})["record_count"] = len(db["records"])
    tmp = root / "data" / "records.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
        f.write("\n")
    tmp.replace(root / "data" / "records.json")
    write_js(db, root)
    write_csv(db, root)
    save.n_pages = write_record_pages(db, root)
    write_sitemap(db, root)
    write_sqlite(db, root)
    write_history_md(root)
    write_readme(db, root)
    write_definitions_csv(db, root)
    try:
        import export_xlsx
        export_xlsx.write_xlsx(db, root)
        save.xlsx_written = True
    except ImportError:  # openpyxl is optional; CSV and SQLite are always written
        save.xlsx_written = False


def main():
    db = load()
    errors, _ = validate.run(db)
    if errors:
        print("Not building: fix the %d error(s) above in data/records.json first (or run tools/validate.py)." % len(errors))
        return 1
    save(db)
    counts = {}
    for r in db["records"]:
        s = r["local_copy"]["status"]
        counts[s] = counts.get(s, 0) + 1
    print("Built data/records.js, data/records.csv, data/register.sqlite%s from %d records." % (
        ", data/register.xlsx" if getattr(save, "xlsx_written", False) else " (no register.xlsx: pip install openpyxl)",
        len(db["records"])))
    print("Built records/ (%d static pages) and sitemap.xml." % getattr(save, "n_pages", 0))
    print("Local copies: " + ", ".join("%s %d" % (k, counts[k]) for k in LOCAL_STATUSES if k in counts))


if __name__ == "__main__":
    sys.exit(main())
