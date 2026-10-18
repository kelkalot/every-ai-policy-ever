# Run 2026-10-18-fix-related-links

Type: fix. Scope: every record. Made by a script, with no agent judgment; merged with `tools/merge.py`.

The data check of 18 October 2026 (`docs/quality-check-2026-10-18.md`) found 223 related links that pointed one way only: record A listed B, but B did not list A. Almost all came from version 1, made before `pipeline.py assemble` made new links two-way. This pass adds each missing reverse link, so that every link is two-way, and changes nothing else.

## Summary

- Added: 0; fields changed: 79 in 79 record(s) (`related` only); re-verified without change: 0
- 223 reverse links added; afterwards no record has a one-way or dangling related link.
- Each change is a `changed` event for the field `related` in `data/history.jsonl`, with the IDs of the records that link to it as the reason.

The pass is `pass.json` in this folder. `tools/validate.py` now warns about one-way links, so a new one shows up in the next build.
