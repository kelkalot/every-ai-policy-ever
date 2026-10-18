#!/usr/bin/env python3
"""The definitions layer of the crosswalk (issue #70): defined terms quoted verbatim from the stored sources of
records, checked by script and compared between two independent extractions.

    python3 tools/definitions.py textify --run RUN   # text of the stored files of the records in RUN/plan.json
    python3 tools/definitions.py check   --run RUN   # every quote in definitions/ and definitions-blind/ against its file
    python3 tools/definitions.py compare --run RUN   # agreement between the two extractions
    python3 tools/definitions.py merge   --run RUN   # add the checked definitions to data/definitions.json
    python3 tools/definitions.py report  --run RUN   # RUN/report.md with the definitions side by side
    python3 tools/definitions.py queue               # records due for a compare run, and why

A compare run is created with `python3 tools/pipeline.py new --type compare`, which writes RUN/run.json (the steps
and who runs each) and RUN/plan.json; `pipeline.py status --run RUN` shows which steps are done. Its checker writes
RUN/checks/<RECORD>.json: {"record_id": "EU-03", "definitions": [{"term_group": "AI system", "verdict": "accept |
reject", "reason": "...", "group_ok": true}], "missed": [{"term_group": "...", "note": "..."}]}, and merge takes only
definitions both extractions agree on, the script check passes and the checker accepts. Runs made before compare
runs existed have no run.json and no checker.

data/definitions.json keeps, besides the definitions, "compared": {RECORD: {"run_id", "date", "files": {path:
sha256}}}, the stored files each record was last compared against. A definition keeps its ID when a later run
quotes it again; a changed text is logged in data/history.jsonl (definition-added, definition-changed).

RUN/plan.json: {"records": ["EU-03", ...], "term_groups": ["AI system", "model"],
                "ocr_lang": {"VN-02": "vie+eng"}}   # optional: the OCR language of a record's scans (default --ocr-lang)
RUN/definitions/<RECORD>.json (and definitions-blind/ for the second extraction):
  {"record_id": "EU-03", "definitions": [{"term": "AI system", "term_group": "AI system",
    "definition": "<verbatim>", "english": "<only when the text is not English>", "english_by": "issuer | agent",
    "file": "archive/...", "sha256": "...", "locator": "Article 3(1)", "language": "English"}],
   "not_found": ["model"], "note": "..."}
A definition quoted from a scan carries text_layer ("ocr (tesseract, vie+eng)") in data/definitions.json: the quote is
verbatim from the OCR text, which can differ from the printed text by a letter or a diacritic.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402  (same folder)

ROOT = P.ROOT
DEFS = ROOT / "data" / "definitions.json"
TERM_GROUPS = ["AI system", "artificial intelligence", "model", "AI model", "general-purpose AI model",
               "automated decision system", "generative AI", "high-risk AI system", "frontier model", "foundation model",
               "provider", "deployer"]
# the groups a compare run looks for; "provider" and "deployer" are parked (issue #70 tracker)
DEFAULT_GROUPS = ["AI system", "artificial intelligence", "AI model", "model", "high-risk AI system", "frontier model",
                  "foundation model", "generative AI", "general-purpose AI model", "automated decision system"]
MAX_QUOTE = 1200  # a definition is the data itself, so it may be longer than an evidence quote
LINE_NO = re.compile(r"(?m)^[ \t]*\d{1,4}[ \t]+")  # margin line numbers of a printed bill


def run_dir(run):
    d = ROOT / "runs" / run
    if not (d / "plan.json").is_file():
        raise SystemExit("runs/%s/plan.json is missing" % run)
    return d, P.read_json(d / "plan.json")


def record_files(db, rid):
    rec = {r["id"]: r for r in db["records"]}.get(rid)
    if not rec:
        raise SystemExit("No record %s" % rid)
    out = {}
    for f in (rec.get("local_copy") or {}).get("files") or []:
        for path, digest in ((f.get("path"), f.get("sha256")), (f.get("previous_path"), f.get("previous_sha256"))):
            if path and (ROOT / path).is_file():
                out[path] = digest
    return out


def current_files(rec, on_disk=True):
    """path -> sha256 of the record's current stored files (not stale; on disk unless on_disk=False)."""
    return {f["path"]: f.get("sha256") for f in (rec.get("local_copy") or {}).get("files") or []
            if f.get("path") and not f.get("stale") and (not on_disk or (ROOT / f["path"]).is_file())}


def source_changed(db, items, on_disk=True):
    """IDs of definitions whose file and SHA-256 are no longer a current stored file of their record."""
    by = {r["id"]: r for r in db["records"]}
    return {x["id"] for x in items
            if current_files(by.get(x["record_id"]) or {}, on_disk).get(x.get("file")) != x.get("sha256")}


def compare_queue(db, reg=None, on_disk=True):
    """[(record_id, [reasons])] due for a compare run, most urgent first: a definition whose source changed, a
    record whose stored files changed since it was compared, then records never compared that have stored text.
    on_disk=False works from records.json alone, as on a machine without archive/."""
    reg = reg if reg is not None else (P.read_json(DEFS, {}) or {})
    items, seen = reg.get("definitions") or [], reg.get("compared") or {}
    changed = source_changed(db, items, on_disk)
    out = []
    for r in db["records"]:
        rid, cur = r["id"], current_files(r, on_disk)
        if not cur:
            continue
        stale = sorted(x["id"] for x in items if x["record_id"] == rid and x["id"] in changed)
        if stale:
            out.append((0, rid, ["the source of %s changed after it was quoted" % ", ".join(stale)]))
        elif rid in seen and any((seen[rid].get("files") or {}).get(f) != h for f, h in cur.items()):
            # a current file the run did not read, or read with another hash
            out.append((1, rid, ["stored files changed since run %s" % seen[rid].get("run_id")]))
        elif rid not in seen:
            out.append((2 if r.get("legal_force") == "Binding" else 3, rid, ["not compared yet"]))
    out.sort(key=lambda t: (t[0], t[1]))
    return [(rid, why) for _, rid, why in out]


def cmd_queue(args):
    db = P.load_db()
    due = compare_queue(db)
    for rid, why in due[:args.limit]:
        print("%-12s %s" % (rid, "; ".join(why)))
    kinds = {}
    for _, why in due:
        k = "never compared" if why == ["not compared yet"] else "changed"
        kinds[k] = kinds.get(k, 0) + 1
    print("%d record(s) due (%s). Start a run: python3 tools/pipeline.py new --type compare [--limit N]"
          % (len(due), ", ".join("%d %s" % (n, k) for k, n in sorted(kinds.items())) or "none"))
    return 0


def text_path(d, path):
    return d / "texts" / (path.replace("archive/", "", 1).replace("/", "__") + ".txt")


def cmd_textify(args):
    d, plan = run_dir(args.run)
    db = P.load_db()
    rows = []
    for rid in plan["records"]:
        for path, digest in record_files(db, rid).items():
            src, out = ROOT / path, text_path(d, path)
            ext, method = src.suffix.lower(), None
            if ext not in (".pdf", ".html", ".htm", ".xml", ".txt") + P.WORD_EXTS:
                continue
            text, _, method, _ = P.file_text(src, (plan.get("ocr_lang") or {}).get(rid, args.ocr_lang))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            rows.append(dict({"record_id": rid, "file": path, "sha256": digest, "text": str(out.relative_to(ROOT)),
                              "chars": len(text)}, **({"method": method} if method and method.startswith("ocr") else {})))
    P.write_json(d / "texts.json", {"files": rows})
    print("Text for %d file(s) of %d record(s); listed in runs/%s/texts.json" % (len(rows), len(plan["records"]), args.run))
    return 0


def locator_key(loc):
    """The article or section numbers of a locator, so that "Art. 3(1)" and "Article 3(1), page 46" agree."""
    s = P.re.sub(r"\bpages?\s*\d+", " ", (loc or "").lower())
    toks = P.re.findall(r"\d+|\b[ivxlc]+\b", s)
    return tuple(toks[:2]) if toks else (P.loose(s)[:12],)


def load_extractions(d, sub):
    return {p.stem: P.read_json(p) for p in sorted((d / sub).glob("*.json"))}


def check_one(db, d, texts, rid, item):
    problems = []
    files = record_files(db, rid)
    path, quote = item.get("file") or "", item.get("definition") or ""
    if item.get("term_group") not in TERM_GROUPS:
        problems.append("term_group %r is not in the vocabulary" % item.get("term_group"))
    if path not in files:
        problems.append("%s is not a stored file of %s" % (path, rid))
    elif (files[path] or "") != (item.get("sha256") or ""):
        problems.append("the SHA-256 does not match the stored file")
    if not quote or len(quote) > MAX_QUOTE:
        problems.append("the definition is empty or longer than %d characters" % MAX_QUOTE)
    if path in files and quote:
        tp = text_path(d, path)
        if path not in texts:
            raw = tp.read_text(encoding="utf-8") if tp.is_file() else ""
            # a bill printed with line numbers: the number that starts a line is not part of the text
            texts[path] = (P.norm_text(raw), P.norm_text(LINE_NO.sub("", raw)))
        body, unnumbered = texts[path]
        if not body:
            problems.append("no text layer for %s (run textify)" % path)
        elif not any(P.norm_text(quote) in b or P.loose(quote) in P.loose(b) for b in (body, unnumbered)):
            problems.append("the definition is not found in the stored text")
    if not item.get("locator"):
        problems.append("no locator")
    return problems


def cmd_check(args):
    d, plan = run_dir(args.run)
    db, texts, result, bad = P.load_db(), {}, {}, 0
    for sub in ("definitions", "definitions-blind"):
        for rid, ex in load_extractions(d, sub).items():
            for i, item in enumerate(ex.get("definitions") or []):
                problems = check_one(db, d, texts, rid, item)
                result.setdefault(sub, {}).setdefault(rid, []).append({"index": i, "term": item.get("term"),
                                                                       "ok": not problems, "problems": problems})
                bad += bool(problems)
                if problems:
                    print("%-18s %-8s %-28s %s" % (sub, rid, (item.get("term") or "")[:28], "; ".join(problems)))
    P.write_json(d / "check.json", result)
    n = sum(len(v) for s in result.values() for v in s.values())
    print("%d definition(s) checked, %d with problems. Written runs/%s/check.json" % (n, bad, args.run))
    return 1 if bad else 0


def cmd_compare(args):
    d, plan = run_dir(args.run)
    a, b = load_extractions(d, "definitions"), load_extractions(d, "definitions-blind")
    pairs, rows = 0, []
    agree_text = agree_loc = 0
    for rid in sorted(set(a) & set(b)):
        by_a = {x.get("term_group"): x for x in a[rid].get("definitions") or []}
        by_b = {x.get("term_group"): x for x in b[rid].get("definitions") or []}
        for g in sorted(set(by_a) | set(by_b)):
            x, y = by_a.get(g), by_b.get(g)
            if not (x and y):
                rows.append({"record_id": rid, "term_group": g, "text": "only in %s" % ("first" if x else "blind"),
                             "locator": None})
                pairs += 1
                continue
            lx, ly = P.loose(x["definition"]), P.loose(y["definition"])
            same = lx == ly or (min(len(lx), len(ly)) > 40 and (lx in ly or ly in lx))
            loc = locator_key(x.get("locator")) == locator_key(y.get("locator"))
            pairs += 1
            agree_text += same
            agree_loc += loc
            rows.append({"record_id": rid, "term_group": g, "text": "same" if same else "differs",
                         "locator": "same" if loc else "differs"})
    out = {"pairs": pairs, "same_definition": agree_text, "same_locator": agree_loc, "rows": rows}
    P.write_json(d / "agreement.json", out)
    for r in rows:
        print("%-8s %-26s definition %-14s locator %s" % (r["record_id"], r["term_group"], r["text"], r["locator"]))
    print("Agreement: %d of %d pairs quote the same definition, %d the same locator." % (agree_text, pairs, agree_loc))
    return 0


def checker_verdicts(d):
    """{(record_id, term_group): verdict} from RUN/checks/, or None when the run has no checker step."""
    run = P.read_json(d / "run.json", {}) or {}
    if run.get("type") != "compare":
        return None  # a run made before compare runs existed
    out = {}
    for rid, ch in load_extractions(d, "checks").items():
        for v in ch.get("definitions") or []:
            out[(rid, v.get("term_group"))] = v
    return out


def cmd_merge(args):
    import history as H  # noqa: E402  (same folder)
    d, plan = run_dir(args.run)
    run = P.read_json(d / "run.json", {}) or {}
    stage = (run.get("stages") or {}).get("extract") or {}
    check = P.read_json(d / "check.json", {}) or {}
    agreed = {(r["record_id"], r["term_group"]) for r in (P.read_json(d / "agreement.json", {}) or {}).get("rows") or []
              if r.get("text") == "same"}
    verdicts = checker_verdicts(d)
    if verdicts is not None and not verdicts:
        raise SystemExit("No checker verdicts in runs/%s/checks/: the checker step comes before merge" % args.run)
    reg = P.read_json(DEFS, {}) or {}
    reg.setdefault("about", "Defined terms quoted verbatim from the stored sources of records (issue #70), checked by "
                            "tools/definitions.py. Similar definitions are not legally equivalent; nothing here is "
                            "legal advice.")
    items = reg.setdefault("definitions", [])
    by_key = {(x["record_id"], x["term_group"]): x for x in items}
    n = max([int(x["id"][1:]) for x in items] + [0])
    ocr = {t["file"]: t["method"] for t in (P.read_json(d / "texts.json", {}) or {}).get("files") or [] if t.get("method")}
    fields = ("term", "term_group", "definition", "english", "english_by", "language", "locator", "file", "sha256")
    events, added, changed, confirmed, held = [], 0, 0, 0, 0
    ev = lambda rid, kind, field, old, new, why: events.append(H.event(  # noqa: E731
        rid, kind, run_id=args.run, field=field, old=old, new=new, reason=why, tool=stage.get("tool"),
        model=stage.get("model")))
    for rid, ex in load_extractions(d, "definitions").items():
        oks = {c["index"] for c in (check.get("definitions") or {}).get(rid) or [] if c["ok"]}
        for i, item in enumerate(ex.get("definitions") or []):
            key = (rid, item.get("term_group"))
            if i not in oks or key not in agreed:
                continue
            if verdicts is not None and (verdicts.get(key) or {}).get("verdict") != "accept":
                held += 1
                continue
            new = dict({k: item.get(k) for k in fields}, **({"text_layer": ocr[item["file"]]} if item.get("file") in ocr else {}))
            old = by_key.get(key)
            if old is None:
                n += 1
                row = dict({"id": "D%04d" % n, "record_id": rid}, **new, run_id=args.run)
                items.append(row)
                by_key[key] = row
                added += 1
                ev(rid, "definition-added", "definition %s (%s)" % (row["id"], key[1]), None, new["definition"],
                   "quoted alike by two extractions and checked against %s" % new["file"])
            elif old.get("run_id") == args.run:
                continue  # merged before from this run
            elif P.loose(old.get("definition")) == P.loose(new["definition"]):
                if (old.get("file"), old.get("sha256")) != (new["file"], new["sha256"]):
                    old.update({k: new[k] for k in ("file", "sha256", "locator")}, run_id=args.run)
                    old.pop("text_layer", None)
                    old.update({k: v for k, v in new.items() if k == "text_layer"})
                    confirmed += 1
                    ev(rid, "re-verified", "definition %s (%s)" % (old["id"], key[1]), None, None,
                       "the same wording quoted again from %s" % new["file"])
            else:
                text_before = old.get("definition")
                for k in list(old):
                    if k not in ("id", "record_id"):
                        old.pop(k)
                old.update(new, run_id=args.run)
                changed += 1
                ev(rid, "definition-changed", "definition %s (%s)" % (old["id"], key[1]), text_before, new["definition"],
                   "quoted again from %s" % new["file"])
    db = P.load_db()
    by = {r["id"]: r for r in db["records"]}
    seen = reg.setdefault("compared", {})
    files = {}
    for t in (P.read_json(d / "texts.json", {}) or {}).get("files") or []:
        files.setdefault(t["record_id"], {})[t["file"]] = t["sha256"]
    for rid in plan["records"]:
        if rid in by:  # the stored files this run compared; the queue looks for changes against them
            seen[rid] = {"run_id": args.run, "date": args.run[:10], "files": files.get(rid) or {}}
    reg["compared"] = dict(sorted(seen.items()))
    if not args.dry_run:
        P.write_json(DEFS, reg)
        H.append(events)
    print("%d added, %d changed, %d re-verified%s in data/definitions.json%s" % (
        added, changed, confirmed, (", %d held back by the checker" % held) if held else "",
        " (dry run)" if args.dry_run else ""))
    return 0


def cmd_report(args):
    d, plan = run_dir(args.run)
    db = P.load_db()
    by = {r["id"]: r for r in db["records"]}
    reg = P.read_json(DEFS, {}) or {}
    agr = P.read_json(d / "agreement.json", {}) or {}
    mine = [x for x in reg.get("definitions") or [] if x.get("run_id") == args.run]
    L = ["# Definitions %s" % args.run, "",
         "Defined terms quoted verbatim from the stored sources of %d records (issue #70). Every quote was checked "
         "against its stored file and SHA-256 by `tools/definitions.py check`. Similar definitions are not legally "
         "equivalent; nothing here is legal advice." % len(plan["records"]), "",
         "**Repeatability:** %s of %s pairs from two independent extractions quote the same definition, %s the same "
         "locator." % (agr.get("same_definition"), agr.get("pairs"), agr.get("same_locator")), ""]
    verdicts = checker_verdicts(d)
    if verdicts is not None:
        agreed = [(r["record_id"], r["term_group"]) for r in agr.get("rows") or [] if r.get("text") == "same"]
        acc = [k for k in agreed if (verdicts.get(k) or {}).get("verdict") == "accept"]
        groups = [(k, v) for k, v in sorted(verdicts.items()) if v.get("group_ok") is False]
        L += ["**Checker:** accepted %d of %d definitions both extractions agree on. Term-group assignments for a "
              "human: %d." % (len(acc), len(agreed), len(groups)), ""]
        L += ["- %s, %s: rejected (%s)" % (k[0], k[1], (verdicts.get(k) or {}).get("reason") or "no verdict")
              for k in agreed if k not in acc]
        L += ["- %s, %s: term group for a human (%s)" % (k[0], k[1], v.get("reason") or "") for k, v in groups]
        missed = [(rid, m) for rid, ch in load_extractions(d, "checks").items() for m in ch.get("missed") or []]
        L += ["- %s: the checker found a definition both extractions missed: %s (%s)" % (rid, m.get("term_group"),
                                                                                        m.get("note") or "")
              for rid, m in missed]
        L += [""] if (len(acc) < len(agreed) or groups or missed) else []
    run = P.read_json(d / "run.json", {}) or {}
    tokens = [((run.get("stages") or {}).get(s) or {}).get("tokens") for s in ("extract", "blind", "check")]
    if any(tokens):
        L += ["**Effort:** about %s tokens per record for extraction, blind extraction and check together (%s)."
              % (format(sum(t or 0 for t in tokens) // max(len(plan["records"]), 1), ","),
                 ", ".join("%s %s" % (s, format(t, ",")) for s, t in zip(("extract", "blind", "check"), tokens) if t)), ""]
    earlier = [x for x in reg.get("definitions") or [] if x["record_id"] in set(plan["records"]) and x.get("run_id") != args.run]
    if earlier and run.get("type") == "compare":
        L += ["**Earlier definitions not quoted again in this run** (they stay as they are; the app marks one whose "
              "source changed): %s." % ", ".join("%s (%s, %s)" % (x["id"], x["record_id"], x["term_group"]) for x in earlier), ""]
    scans = sorted({(x["record_id"], x["text_layer"]) for x in mine if x.get("text_layer")})
    if scans:
        L += ["**Text from OCR:** %s. These quotes are verbatim from the OCR text of a scan, which can differ from the "
              "printed text by a letter or a diacritic." % "; ".join("%s, %s" % s for s in scans), ""]
    for g in TERM_GROUPS:
        rows = [x for x in mine if x["term_group"] == g]
        if not rows:
            continue
        L += ["## %s" % g, "", "| Record | Term | Definition | Where |", "|---|---|---|---|"]
        for x in rows:
            text = x["definition"].replace("|", "\\|").replace("\n", " ")
            if x.get("english"):
                text += " *(English%s: %s)*" % (" by the issuer" if x.get("english_by") == "issuer" else
                                               ", agent's rendering", x["english"].replace("|", "\\|"))
            L.append("| %s %s | %s | %s | %s |" % (x["record_id"], (by.get(x["record_id"]) or {}).get("short_title", ""),
                                                   x["term"], text, x["locator"]))
        L.append("")
    review = [r for r in agr.get("rows") or [] if r.get("text") != "same"]
    if review:
        L += ["## For review: found by one extraction only, or quoted differently", "",
              "These are not in `data/definitions.json`; only definitions both extractions found and quoted alike are.", ""]
        L += ["- %s, %s: %s" % (r["record_id"], r["term_group"], r["text"]) for r in review] + [""]
    missing = [(rid, ex.get("not_found")) for rid, ex in load_extractions(d, "definitions").items() if ex.get("not_found")]
    if missing:
        L += ["## Not found in the stored text", "",
              "Not found means only that the stored files do not define the term: where they are a press release or a "
              "status page rather than the instrument's text (the extraction's note says so), that text has to be "
              "archived before a later run can look again.", ""] + ["- %s: %s" % (rid, ", ".join(nf)) for rid, nf in missing] + [""]
    (d / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("Written runs/%s/report.md (%d definitions)" % (args.run, len(mine)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Definitions layer of the crosswalk (issue #70).")
    sub = ap.add_subparsers(dest="cmd")
    q = sub.add_parser("queue")
    q.add_argument("--limit", type=int, default=30)
    for name in ("textify", "check", "compare", "merge", "report"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
        if name == "textify":
            s.add_argument("--ocr-lang", default="eng")
        if name == "merge":
            s.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 1
    return {"textify": cmd_textify, "check": cmd_check, "compare": cmd_compare, "merge": cmd_merge,
            "report": cmd_report, "queue": cmd_queue}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
