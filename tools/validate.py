#!/usr/bin/env python3
"""Check data/records.json for schema, vocabulary and consistency problems.

    python3 tools/validate.py             # report problems; exit code 1 if there are errors
    python3 tools/validate.py --strict    # warnings count as errors too

tools/build.py runs the same checks and refuses to build when there are errors, so a
typo in a status value or a dangling related ID cannot reach the app unnoticed.

Errors are things the app or the archiver cannot handle: missing required fields, values
outside the controlled vocabularies, malformed dates, duplicate IDs, related IDs that do
not exist. Warnings are things a human should look at: partial dates, an "in force"
record with no in-force date, http-only URLs, two records sharing an official URL,
level-C verification.

Standard library only. Python 3.8+.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = ["id", "slug", "title", "short_title", "jurisdiction", "country", "jurisdiction_level", "region",
            "issuing_body", "instrument_type", "legal_force", "status", "language", "summary",
            "safety_topics", "verification"]
OPTIONAL = ["original_title", "date_published", "date_in_force", "date_last_updated", "official_identifier",
            "official_url", "secondary_url", "related", "notes", "scope_note", "english_version", "local_copy"]

VOCAB = {
    "instrument_type": ["Law", "Regulation / implementing rule", "Executive order / decree", "Guidelines / framework",
                        "Voluntary code / commitments", "Technical standard", "Institutional mandate",
                        "Declaration / statement", "Treaty / convention", "Resolution", "Bill / draft law",
                        "Strategy / action plan", "Report (government-commissioned)", "Supervisory statement / letter"],
    "legal_force": ["Binding", "Non-binding", "Proposed"],
    "status": ["In force", "Partially in force", "Adopted, not yet in force", "Published (non-binding, current)",
               "Draft / proposed", "Superseded", "Revoked / withdrawn", "Lapsed"],
    "jurisdiction_level": ["International", "Supranational", "National", "Sub-national"],
    "region": ["Global", "Europe", "North America", "Latin America & Caribbean", "East Asia",
               "South & Southeast Asia", "Central Asia", "Oceania", "Middle East & North Africa",
               "Sub-Saharan Africa"],
}
VERIFICATION_LEVELS = ["A", "B", "C"]
LOCAL_STATUSES = ["archived", "archived-review", "partial", "failed", "no-url", "not-attempted"]
TOPICS = ["accountability & liability", "evaluation & testing", "transparency & labelling",
          "general-purpose / frontier AI", "human oversight", "international cooperation", "risk-based classification",
          "deepfakes & synthetic media", "public-sector use", "catastrophic risk", "safety institute",
          "incident reporting", "research priorities", "national security & military", "child safety",
          "prohibited practices", "critical infrastructure"]

# english_version.kind: is there an English text, and whose? "authentic": the issuer adopted or published the
# instrument in English as one of its own texts; "government translation": an English translation published by the
# issuer or another public body (ministry, government law-translation service, public research institute), usually
# provisional or for reference, without legal force; "third-party translation": by anyone else (university, law firm,
# translation project, commercial database); "none found". The kinds say who translated, not that a text is binding.
ENGLISH_VERSION_KINDS = ["authentic", "government translation", "third-party translation", "none found"]
TRANSLATION_KINDS = {"government translation", "third-party translation"}
LANGUAGE_REMARK = re.compile(r"[();]|translat|availab|not confirmed|review|overview|heading|working languages"
                             r"|\btitle\b|\bsummary\b|\bsite\b", re.I)
LANGUAGE_VARIANT = re.compile(r"\s*\((Traditional|Simplified)\)")

FULL_DATE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
PARTIAL_DATE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?$")
ID_FORMAT = re.compile(r"^[A-Z0-9]{2,6}(-[A-Z]{2})?-\d{2}$")
SLUG_FORMAT = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
IN_FORCE_STATUSES = {"In force", "Partially in force"}


def has_english_text(r):
    """True when English is among the languages of the official text (the EU's 24 languages include it)."""
    lang = r.get("language") or ""
    return lang.startswith("All 24 official EU languages") or any(x.strip().lower().startswith("english")
                                                                   for x in lang.split(","))


def frame_names():
    """code -> (level, name) from pipeline/frame.json, the reference spelling of jurisdiction and country names."""
    try:
        f = json.loads((ROOT / "pipeline" / "frame.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {j["code"]: (j.get("level"), j.get("name")) for j in f.get("jurisdictions") or []}


def check(db):
    """Return a list of (level, record_id, message); level is 'error' or 'warning'."""
    out = []
    err = lambda rid, msg: out.append(("error", rid, msg))
    warn = lambda rid, msg: out.append(("warning", rid, msg))

    records = db.get("records")
    if not isinstance(records, list) or not records:
        err("-", "records.json has no 'records' list")
        return out
    meta = db.get("meta") or {}
    for k in ("name", "version", "snapshot_date"):
        if not meta.get(k):
            err("-", "meta.%s is missing" % k)
    if meta.get("snapshot_date") and not FULL_DATE.match(str(meta["snapshot_date"])):
        err("-", "meta.snapshot_date is not a full ISO date")

    ids = [r.get("id") for r in records]
    id_set = set(i for i in ids if i)
    for dup, n in Counter(ids).items():
        if n > 1:
            err(dup or "-", "duplicate record id (%d records)" % n)
    for dup, n in Counter(r.get("slug") for r in records).items():
        if n > 1 and dup:
            err("-", "duplicate slug %r (%d records)" % (dup, n))
    for url, n in Counter(r.get("official_url") for r in records).items():
        if n > 1 and url:
            who = ", ".join(r["id"] for r in records if r.get("official_url") == url)
            warn(who, "share the same official_url; check that each points at its own document")
    links = {r.get("id"): {x.get("id") if isinstance(x, dict) else x for x in r.get("related") or []} for r in records}
    for a, targets in links.items():
        for b in sorted(t for t in targets if t in links and a not in links[t] and t != a):
            warn(b, "related link from %s is one-way; %s should list %s too (pipeline.py assemble makes links two-way)"
                 % (a, b, a))

    names = frame_names()
    for r in records:
        rid = r.get("id") or "<no id>"
        if rid != "<no id>" and not ID_FORMAT.match(rid):
            warn(rid, "id does not follow <JURISDICTION>[-<SUB>]-<NN>")
        for k in REQUIRED:
            v = r.get(k)
            if v is None or v == "" or v == []:
                err(rid, "required field %r is missing or empty" % k)
        for k in r:
            if k not in REQUIRED and k not in OPTIONAL:
                warn(rid, "unknown field %r" % k)
        if r.get("slug") and not SLUG_FORMAT.match(r["slug"]):
            err(rid, "slug %r is not lower-case-with-hyphens" % r["slug"])
        for field, allowed in VOCAB.items():
            v = r.get(field)
            if v is not None and v not in allowed:
                err(rid, "%s %r is not in the vocabulary (%s)" % (field, v, ", ".join(allowed)))
        for t in r.get("safety_topics") or []:
            if t not in TOPICS:
                warn(rid, "safety topic %r is not in the shared topic list; add it to tools/validate.py if it is new" % t)
        if r.get("scope_note") is not None and (not isinstance(r["scope_note"], str) or not r["scope_note"].strip()):
            err(rid, "scope_note must be text saying why the record is borderline, or absent for a clearly in-scope record")
        if r.get("safety_topics") and not isinstance(r["safety_topics"], list):
            err(rid, "safety_topics must be a list")

        # languages and translation
        lang = r.get("language") or ""
        if lang and LANGUAGE_REMARK.search(LANGUAGE_VARIANT.sub("", lang)):
            warn(rid, "language %r holds a remark; give the language names only, and record an English translation "
                      "in english_version" % lang)
        ev = r.get("english_version")
        if ev is not None:
            if not isinstance(ev, dict) or ev.get("kind") not in ENGLISH_VERSION_KINDS:
                err(rid, "english_version must be {\"kind\", \"url\", \"by\"} with kind one of %s"
                    % ", ".join(ENGLISH_VERSION_KINDS))
            else:
                for k in ev:
                    if k not in ("kind", "url", "by"):
                        warn(rid, "english_version has an unknown key %r" % k)
                if ev.get("url") and not re.match(r"^https?://\S+$", ev["url"]):
                    err(rid, "english_version.url %r is not an http(s) URL" % ev["url"])
                if ev["kind"] in TRANSLATION_KINDS and not (ev.get("url") and ev.get("by")):
                    warn(rid, "english_version is a translation but lacks its url or who made it ('by')")
                if ev["kind"] == "none found" and ev.get("url"):
                    warn(rid, "english_version is 'none found' but has a url")
                if ev["kind"] == "authentic" and lang and not has_english_text(r):
                    warn(rid, "english_version is 'authentic' but English is not among the languages in 'language'")
        if lang and not has_english_text(r):
            if not r.get("original_title"):
                warn(rid, "the official text is not in English but original_title is empty")
            if ev is None:
                warn(rid, "the official text is not in English and english_version is not recorded yet")

        # names: jurisdiction (and country, for national records) are spelled as in pipeline/frame.json
        code = re.sub(r"-\d+$", "", rid)
        if code in names:
            level, name = names[code]
            if level in ("National", "Sub-national") and name and r.get("jurisdiction") != name:
                warn(rid, "jurisdiction %r is spelled %r in pipeline/frame.json" % (r.get("jurisdiction"), name))
            if level == "National" and name and r.get("country") != name:
                warn(rid, "country %r is spelled %r in pipeline/frame.json" % (r.get("country"), name))

        for k in ("date_published", "date_in_force", "date_last_updated"):
            v = r.get(k)
            if v is None:
                continue
            v = str(v)
            if FULL_DATE.match(v):
                continue
            if PARTIAL_DATE.match(v):
                warn(rid, "%s %r is a partial date (only the year or month is known); fine if that is all the source gives" % (k, v))
            else:
                err(rid, "%s %r is not an ISO date (YYYY-MM-DD, or YYYY-MM / YYYY when the day is unknown)" % (k, v))
        if not r.get("date_published"):
            warn(rid, "date_published is empty; the record sorts last and is left out of the year chart. Say in the notes why no date is known")
        dp, di = str(r.get("date_published") or ""), str(r.get("date_in_force") or "")
        if dp and di and FULL_DATE.match(dp) and FULL_DATE.match(di) and di < dp:
            warn(rid, "date_in_force %s is before date_published %s; correct for some instruments, check the notes" % (di, dp))
        if r.get("status") in IN_FORCE_STATUSES and not r.get("date_in_force"):
            warn(rid, "status is %r but date_in_force is empty" % r["status"])
        if r.get("legal_force") == "Binding" and r.get("status") == "Draft / proposed":
            warn(rid, "legal_force Binding with status 'Draft / proposed' looks inconsistent")
        if r.get("legal_force") == "Proposed" and r.get("status") in IN_FORCE_STATUSES:
            warn(rid, "legal_force Proposed with an in-force status looks inconsistent")

        for k in ("official_url", "secondary_url"):
            u = r.get(k)
            if not u:
                continue
            if not re.match(r"^https?://\S+$", u):
                err(rid, "%s %r is not an http(s) URL" % (k, u))
            elif u.startswith("http://"):
                warn(rid, "%s uses plain http; keep it only if the site has no working https" % k)
        if not r.get("official_url"):
            warn(rid, "no official_url; the record cannot be archived and is level %s" % ((r.get("verification") or {}).get("level")))

        v = r.get("verification") or {}
        if isinstance(v, dict):
            if v.get("level") not in VERIFICATION_LEVELS:
                err(rid, "verification.level %r must be A, B or C" % v.get("level"))
            if not v.get("verified_on") or not FULL_DATE.match(str(v.get("verified_on"))):
                err(rid, "verification.verified_on must be a full ISO date")
            if not v.get("method"):
                err(rid, "verification.method is empty")
            if v.get("level") == "C":
                warn(rid, "verification level C: not confirmed on an official page; re-check before citing")
        elif v:
            err(rid, "verification must be an object")

        for x in r.get("related") or []:
            tid = x.get("id") if isinstance(x, dict) else None
            if not tid:
                err(rid, "related entry without an id")
            elif tid not in id_set:
                err(rid, "related id %r does not exist" % tid)
            elif tid == rid:
                err(rid, "record is related to itself")

        lc = r.get("local_copy")
        if lc and lc.get("status") not in LOCAL_STATUSES:
            err(rid, "local_copy.status %r is not valid" % lc.get("status"))
    return out


def run(db, quiet=False, strict=False):
    problems = check(db)
    errors = [p for p in problems if p[0] == "error"]
    warnings = [p for p in problems if p[0] == "warning"]
    if not quiet:
        for level, rid, msg in problems:
            if level == "error" or strict:
                print("%-8s %-10s %s" % (level.upper(), rid, msg))
        if warnings and not strict:
            kinds = Counter(re.sub(r"'[^']*'|\d{4}-\d{2}(-\d{2})?|%s" % "|".join(sorted(id_set_for(warnings), key=len, reverse=True)), "", m).strip()
                            for _, _, m in warnings)
            print("Warnings: %d (%s). Run tools/validate.py --strict to list them." % (
                len(warnings), "; ".join("%d %s" % (n, k[:60]) for k, n in kinds.most_common(6))))
        print("Validation: %d error(s), %d warning(s) in %d records." % (len(errors), len(warnings), len(db.get("records") or [])))
    return errors, warnings


def id_set_for(problems):
    return {rid for _, rid, _ in problems}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate data/records.json.")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors and list them")
    ap.add_argument("--file", default=str(ROOT / "data" / "records.json"))
    args = ap.parse_args(argv)
    with open(args.file, encoding="utf-8") as f:
        db = json.load(f)
    errors, warnings = run(db, strict=args.strict)
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
