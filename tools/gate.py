#!/usr/bin/env python3
"""The gate: a second, mechanical check of every change to the official data before it reaches main or a release.

    python3 tools/gate.py                  # the working tree against origin/main (what a pull request would change)
    python3 tools/gate.py --base v1.15     # against a tag or commit (the release uses the last release tag)
    python3 tools/gate.py --no-archive     # skip the checks that need the stored documents (CI has none)
    python3 tools/gate.py --quiet          # print only failures and warnings

It runs before a run's commit (the run's "gate" step and the Claude Code hook .claude/hooks/data_gate.py), on every
pull request to main (.github/workflows/gate.yml), and before a release (tools/publish_hf.py --release). It changes
nothing except the generated files, which it rebuilds to see whether they were up to date.

Checks: validation; the history is only appended to; no record or definition is deleted and IDs and slugs stay;
every changed field, new record and new or changed definition has its history event; every run named in the new
history has its folder and report; official-site decisions carry who and when; the generated files are in sync with
the data; no credential in the change; no sync-conflict copy; and, with the stored documents, every changed record's
files and every new evidence quote and definition against its file and SHA-256.

Exit code 0 when everything passes (warnings allowed), 1 when a check fails. Standard library only.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import history as H  # noqa: E402  (same folder)

OFFICIAL = ["data/records.json", "data/history.jsonl", "data/definitions.json", "pipeline/official-sites.json",
            "pipeline/frame.json", "pipeline/leads.json", "pipeline/questions.json", "pipeline/scope-decisions.md"]
GENERATED = ["data/records.js", "data/records.csv", "data/definitions.csv", "HISTORY.md", "README.md", "records",
             "sitemap.xml", "pipeline/coverage.md"]
SECRETS = re.compile(r"\bhf_[A-Za-z0-9]{30,}|\bgh[pousr]_[A-Za-z0-9]{36,}|\bgithub_pat_[A-Za-z0-9_]{40,}|"
                     r"\bsk-(?:proj-|ant-)?[A-Za-z0-9]{32,}|\bAKIA[0-9A-Z]{16}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----")
SYNC_COPY = re.compile(r" \d+(\.[^./]+)?$")
MAX_CHANGED = 40  # records changed in one go without a warning (pipeline.py MAX_RUN)


def git(*args, check=True):
    res = subprocess.run(["git", "-C", str(ROOT)] + list(args), capture_output=True, text=True)
    if check and res.returncode:
        raise SystemExit("git %s failed: %s" % (" ".join(args), res.stderr.strip()))
    return res.stdout


def at_base(base, path):
    res = subprocess.run(["git", "-C", str(ROOT), "show", "%s:%s" % (base, path)], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else None


def jload(text, default=None):
    return json.loads(text) if text else default


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(paths):
    """path -> sha256 of every file under the given paths, to see what a rebuild changes."""
    out = {}
    for p in paths:
        q = ROOT / p
        for f in ([q] if q.is_file() else sorted(q.rglob("*")) if q.is_dir() else []):
            if f.is_file() and not SYNC_COPY.search(f.stem + f.suffix):
                out[str(f.relative_to(ROOT))] = sha256(f)
    return out


class Gate:
    def __init__(self, quiet=False):
        self.results, self.quiet = [], quiet

    def add(self, state, name, detail=""):
        self.results.append((state, name, detail))
        if not self.quiet or state in ("FAIL", "WARN"):
            print("%-4s  %-28s %s" % (state, name, detail))

    def check(self, name, problems, ok_detail="", warn=False):
        if problems:
            self.add("WARN" if warn else "FAIL", name, "%d: %s" % (len(problems), "; ".join(problems[:8]) +
                                                                   (" ..." if len(problems) > 8 else "")))
        else:
            self.add("PASS", name, ok_detail)

    @property
    def failed(self):
        return [r for r in self.results if r[0] == "FAIL"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check every change to the official data before it reaches main.")
    ap.add_argument("--base", default="origin/main", help="what the change is compared with (default origin/main)")
    ap.add_argument("--no-archive", action="store_true", help="skip the checks that need the stored documents")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    base = git("rev-parse", "--verify", "--quiet", args.base + "^{commit}", check=False).strip()
    if not base:
        raise SystemExit("Unknown base %r (fetch first: git fetch origin)" % args.base)
    g = Gate(args.quiet)
    changed = [p for p in git("diff", "--name-only", base).splitlines() if p]
    print("Gate: the working tree against %s (%s); %d changed file(s)." % (args.base, base[:9], len(changed)))

    # 1. validation
    import validate  # noqa: E402  (same folder)
    import build  # noqa: E402  (same folder)
    db = build.normalise(build.load())
    errors, _ = validate.run(db, quiet=True)
    g.check("validation", ["%d validation error(s); run python3 tools/validate.py" % errors] if errors else [],
            "%d records, 0 errors" % len(db["records"]))

    # 2. the history is only appended to
    old_hist = (at_base(base, "data/history.jsonl") or "").splitlines()
    new_hist = (ROOT / "data" / "history.jsonl").read_text(encoding="utf-8").splitlines()
    probs = []
    if new_hist[:len(old_hist)] != old_hist:
        first = next((i for i, (a, b) in enumerate(zip(old_hist, new_hist)) if a != b), min(len(old_hist), len(new_hist)))
        probs.append("an earlier line was changed or removed (line %d); history lines are never edited" % (first + 1))
    new_events = []
    for n, line in enumerate(new_hist[len(old_hist):], len(old_hist) + 1):
        try:
            e = json.loads(line)
        except ValueError:
            probs.append("line %d is not JSON" % n)
            continue
        if [k for k in H.KEYS if k not in e] or e.get("event") not in H.EVENTS:
            probs.append("line %d is malformed" % n)
        new_events.append(e)
    g.check("history append-only", probs, "%d new event(s)" % len(new_events))

    # 3. records are never deleted; IDs and slugs stay
    old_db = jload(at_base(base, "data/records.json"), {"records": []})
    old = {r["id"]: r for r in old_db["records"]}
    new = {r["id"]: r for r in db["records"]}
    probs = ["%s was deleted (a record is never deleted; AGENTS.md rule 7)" % rid for rid in old if rid not in new]
    probs += ["%s changed its slug %s -> %s" % (rid, old[rid].get("slug"), new[rid].get("slug"))
              for rid in old if rid in new and old[rid].get("slug") != new[rid].get("slug")]
    g.check("records kept", probs, "%d before, %d now" % (len(old), len(new)))

    # 4. every change has its history event
    by_rec = {}
    for e in new_events:
        by_rec.setdefault(e.get("record_id"), []).append(e)
    probs, n_changed = [], 0
    for rid, r in new.items():
        evs = by_rec.get(rid) or []
        if rid not in old:
            if not any(e["event"] == "added" for e in evs):
                probs.append("%s is new but has no 'added' event (records are added by tools/merge.py)" % rid)
            continue
        diff = [k for k in set(r) | set(old[rid]) if k != "local_copy" and r.get(k) != old[rid].get(k)]
        n_changed += bool(diff)
        for k in diff:
            if k == "verification":
                ok = bool(evs)
            else:
                ok = any((e.get("field") or "") == k or (e.get("field") or "").startswith(k + ".") for e in evs)
            if not ok:
                probs.append("%s.%s changed without a history event (hand edit?)" % (rid, k))
    g.check("changes logged", probs, "%d record(s) changed, every field logged" % n_changed)
    if n_changed > MAX_CHANGED:
        g.add("WARN", "size", "%d records changed in one go (more than %d); review with care" % (n_changed, MAX_CHANGED))

    # 5. the meta block
    om, nm = old_db.get("meta") or {}, db.get("meta") or {}
    if om.get("snapshot_date") and om.get("snapshot_date") != nm.get("snapshot_date"):
        g.add("WARN", "snapshot date", "%s -> %s: only a recheck of every record may change it"
              % (om.get("snapshot_date"), nm.get("snapshot_date")))

    # 6. definitions: never deleted, IDs stay, every change logged
    od = {x["id"]: x for x in (jload(at_base(base, "data/definitions.json"), {}) or {}).get("definitions") or []}
    nd_reg = jload((ROOT / "data" / "definitions.json").read_text(encoding="utf-8")) \
        if (ROOT / "data" / "definitions.json").is_file() else {}
    nd = {x["id"]: x for x in nd_reg.get("definitions") or []}
    dev = {}
    for e in new_events:
        m = re.match(r"definition (D\d+)", e.get("field") or "")
        if m:
            dev.setdefault(m.group(1), []).append(e["event"])
    probs = ["%s was deleted" % i for i in od if i not in nd]
    for i, x in nd.items():
        if i not in od:
            if "definition-added" not in dev.get(i, []):
                probs.append("%s is new but has no definition-added event" % i)
            continue
        o = od[i]
        if (o["record_id"], o["term_group"]) != (x["record_id"], x["term_group"]):
            probs.append("%s now belongs to another record or term group" % i)
        if o.get("definition") != x.get("definition") and "definition-changed" not in dev.get(i, []):
            probs.append("%s changed its wording without a definition-changed event" % i)
        elif (o.get("file"), o.get("sha256")) != (x.get("file"), x.get("sha256")) and not dev.get(i):
            probs.append("%s changed its file without a history event" % i)
    g.check("definitions kept", probs, "%d before, %d now" % (len(od), len(nd)))

    # 7. provenance: every run named in the new history has its folder and report
    def run_of(r):  # a maintainer's decision carries its question's key: record:<ID>@<run>, sample:<run>, host:<host>
        kind, colon, rest = r.partition(":")
        if not colon:
            return r
        return rest.rsplit("@", 1)[1] if "@" in rest else (rest if kind == "sample" else None)
    runs = sorted({run_of(e["run_id"]) for e in new_events if e.get("run_id")} - {None})
    probs = ["runs/%s/report.md is missing" % r for r in runs if not (ROOT / "runs" / r / "report.md").is_file()]
    g.check("run reports", probs, ", ".join(runs) if runs else "no run in the new history")

    # 8. official sites: decisions are never removed and always say who and when
    key = lambda x: (x.get("code"), x.get("host"))  # noqa: E731
    os_old = {key(x): x for x in (jload(at_base(base, "pipeline/official-sites.json"), {}) or {}).get("sites") or []}
    os_new = {key(x): x for x in (jload((ROOT / "pipeline" / "official-sites.json").read_text(encoding="utf-8"), {})
                                  or {}).get("sites") or []}
    probs = ["%s %s was removed" % k for k in os_old if k not in os_new]
    for k, x in os_new.items():
        if os_old.get(k) != x:
            if x.get("status") not in ("official", "not official", "proposed"):
                probs.append("%s %s has status %r" % (k + (x.get("status"),)))
            if not (x.get("decided_by") and x.get("decided_on")):
                probs.append("%s %s changed without decided_by and decided_on" % k)
    g.check("official sites", probs, "%d entries" % len(os_new))

    # 9. the generated files are in sync with the data
    before = fingerprint(GENERATED)
    subprocess.run([sys.executable, str(ROOT / "tools" / "build.py")], capture_output=True, text=True, cwd=str(ROOT))
    after = fingerprint(GENERATED)
    stale = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    g.check("generated files", ["out of date, now rebuilt by build.py; review and include them: %s" % ", ".join(stale[:6])]
            if stale else [], "in sync with the data")

    # 10. no credential and no sync-conflict copy in the change
    added = [l[1:] for l in git("diff", "--unified=0", base).splitlines() if l.startswith("+") and not l.startswith("+++")]
    hits = sorted({m.group(0)[:6] + "..." for l in added for m in [SECRETS.search(l)] if m})
    g.check("no credentials", ["a credential-like string (%s) in the change; remove it and revoke the credential"
                               % ", ".join(hits)] if hits else [])
    g.check("no sync copies", ["%s looks like a sync-conflict copy" % p for p in changed if SYNC_COPY.search(Path(p).name)])

    # 11. with the stored documents: changed records' files, new evidence and new definitions
    if args.no_archive or not any((ROOT / "archive").glob("*/*")):
        g.add("SKIP", "stored documents", "--no-archive" if args.no_archive else "no archive/ here")
    else:
        import pipeline as P  # noqa: E402  (same folder)
        probs, n = [], 0
        for rid, r in new.items():
            if rid in old and r.get("local_copy") == old[rid].get("local_copy") and not by_rec.get(rid):
                continue
            for f in (r.get("local_copy") or {}).get("files") or []:
                if f.get("stale") or not f.get("path"):
                    continue
                p = ROOT / f["path"]
                n += 1
                if not p.is_file():
                    probs.append("%s: %s is missing" % (rid, f["path"]))
                elif f.get("sha256") and sha256(p) != f["sha256"]:
                    probs.append("%s: %s does not match its SHA-256" % (rid, f["path"]))
        g.check("record files", probs, "%d file(s) of changed records match their SHA-256" % n)
        probs, n = [], 0
        for e in new_events:
            for ev in e.get("evidence") or []:
                if not (isinstance(ev, dict) and ev.get("file")):
                    continue
                p = ROOT / ev["file"]
                n += 1
                if not p.is_file():
                    probs.append("%s: evidence file %s is missing" % (e["record_id"], ev["file"]))
                    continue
                if ev.get("sha256") and sha256(p) != ev["sha256"]:
                    probs.append("%s: %s does not match its SHA-256" % (e["record_id"], ev["file"]))
                txt = p.with_name(p.name + ".txt")
                if ev.get("quote") and txt.is_file():
                    body = txt.read_text(encoding="utf-8", errors="replace")
                    if P.norm_text(ev["quote"]) not in P.norm_text(body) and P.loose(ev["quote"]) not in P.loose(body):
                        probs.append("%s: a quote is not in %s" % (e["record_id"], ev["file"]))
        g.check("evidence", probs, "%d evidence item(s) in the new history checked" % n)
        import definitions as D  # noqa: E402  (same folder)
        probs, n = [], 0
        for i, x in nd.items():
            if od.get(i) == x:
                continue
            p = ROOT / x["file"]
            n += 1
            if not p.is_file() or sha256(p) != x.get("sha256"):
                probs.append("%s: %s is missing or does not match its SHA-256" % (i, x["file"]))
                continue
            tp = D.text_path(ROOT / "runs" / x.get("run_id", ""), x["file"])
            if tp.is_file():
                body = tp.read_text(encoding="utf-8")
                if not any(P.norm_text(x["definition"]) in P.norm_text(b) or P.loose(x["definition"]) in P.loose(b)
                           for b in (body, D.LINE_NO.sub("", body))):
                    probs.append("%s: the definition is not in its stored text" % i)
        g.check("definition quotes", probs, "%d new or changed definition(s) checked" % n)

    bad = g.failed
    print("\nGate %s: %d passed, %d failed, %d warning(s)." % (
        "FAILED" if bad else "passed", sum(1 for r in g.results if r[0] == "PASS"), len(bad),
        sum(1 for r in g.results if r[0] == "WARN")))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
