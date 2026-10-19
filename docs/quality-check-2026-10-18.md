# Quality check after the first monthly recheck, 18 October 2026

Data version 1.17, snapshot 2026-10-18. Between 14 and 18 October 2026, recheck and refresh runs checked every one of the 400 records. Two kinds of check followed: scripted checks of the data and of what a release uploads, and a count of what the pipeline's own checks found and missed. Agents did the work in Claude Code (coordinator and extractors Claude Opus 5.5, checkers Claude Sonnet 5.5, blind extractors mostly Claude Sonnet 5.5). No human has reviewed the records of this cycle yet (see "Human review" below).

## Scripted checks of the data

| Check | Result |
|---|---|
| `tools/gate.py --base v1.16`, with the stored documents | passed: 350 changed records, 722 stored files and 842 evidence quotes match their files and SHA-256 hashes |
| `tools/archive.py --verify` | no integrity problems in any stored file |
| `tools/history.py --check` | 1,621 events, none malformed |
| `tools/validate.py` | no errors; 131 warnings, mostly partial dates (59) and level C (29) |
| verification dates | every record verified between 14 and 18 October 2026 |

A read-only consistency audit then compared fields with each other. It found the following.

- **Related links:** 223 related links pointed one way only (A lists B, B does not list A). Almost all came from version 1, made before `pipeline.py assemble` made new links two-way. The run `2026-10-18-fix-related-links` added the missing reverse links with `tools/merge.py`, one history event per record (79 records). `tools/validate.py` now warns about a one-way link.
- **Level A with an announcement as `official_url`:** nine level-A records still point `official_url` at an announcement, although their level rests on a stored official register or text. They are six California statutes (US-CA-01, -02, -05, -06, -07, -08), whose level rests on the legislature's weekly histories, and SG-06, INT-02 and ID-02. For the California records, leginfo.legislature.ca.gov refuses the archiver, so moving `official_url` there means a page that cannot be stored, unless a person provides the chaptered text. Eleven further records matched the script's announcement pattern but point at the instrument itself, such as a statement that is the declaration, or a presidential order published on the president's site.
- **Shared and missing `official_url`:** HK-01 and HK-02 share one `official_url`, a landing page (US-CA-01 and US-CA-02 share the Governor's release, as above). PY-02 (level A) and VN-07 (level B) have no `official_url`.
- **Field gaps:**
  - INT-15 has a remark in `language` and no `original_title`.
  - KZ-01, JP-13 and PE-02 are in force but have no `date_in_force`.
  - MY-02, TH-03, CA-ON-02 and US-NV-02 have no `date_published`.
  - CN-16, KZ-01, UA-02 and BJ-01 have no `english_version`, and VN-01 has no `original_title`.

The 25 records in the last four items are queued for the next refresh run as refresh requests, leads L019 to L043, each with its reason. `python3 tools/pipeline.py queue` lists them first.

## Tests of what a release uploads

`tools/release_check.py` tests the files that `tools/publish_hf.py` builds, and `publish_hf.py --release` now runs it before uploading. On the build of version 1.17 the tests found the following.

| Test | Result |
|---|---|
| dataset tables | 400 records, 1,276 related pairs, 1,594 topics, 1,700 history events and 26 definitions, all matching `data/` |
| generated data files | `records.csv`, `records.js`, `register.sqlite` and `register.xlsx` hold the same 400 records |
| archive copies | 819 files match their `SHA256SUMS` lines |
| Space and record pages | 400 pages; every citation names version 1.17 and snapshot 2026-10-18; every internal link resolves; the sitemap lists every page |
| cards | dataset, archive and Space cards filled, with version, snapshot and record count |
| history replay | for 1,520 (record, field) pairs the last logged value is the current value |
| credentials | none in the dataset and Space files |
| app in a headless browser | the index shows all 400 records; a record page renders; no script errors |
| evidence files published | first a warning: 352 of the 662 files quoted as evidence in the history or the definitions were not in the archive dataset, although all are stored (fixed, see below) |

The browser and credential tests were checked against a copy of the build with an error and a fake token planted in it; both failed, as they should.

The missing evidence files are 261 copies that runs stored under `archive/_runs/` and 91 earlier snapshots of record sources that a newer copy replaced. The archive dataset held only each record's current copies, so a reader of the Hugging Face archive could not verify these quotes. From version 1.17 on, `publish_hf.py` also publishes every quoted file except third-party copies: 647 of the 662, with the role `evidence: run copy` or `evidence: earlier snapshot` in `source_files`. The 15 left out are copies from third-party sites (for example CSET and China Law Translate), listed in `source_files` with `in_archive_dataset = false`. The release test now fails when a quoted file that may be published is missing.

The same test run found that `register.sqlite` and `register.xlsx`, which are generated but not in git, were older than the data on the publishing machine; the release would have uploaded the old Excel file. `publish_hf.py` now writes both from the data before it builds the dataset.

## How the pipeline's own checks performed

Recheck and refresh runs from 17 October on (402 checked records):

- **Checker verdicts:** 366 accept (91%), 18 accept with fixes, 18 needs a human, none rejected.
- **Field verdicts (2,964):** 2,825 supported, 91 judgment differs, 48 unsupported, none contradicted.
- **Repeatability:** on the records each sample produced, a blind second extraction agreed with the first on 91.2% to 100% of the field values, 96.0% on average over 14 runs.

The checkers' newer-version searches found real changes:

- the two 2026 amending acts of the California AI Transparency Act (US-CA-02);
- the renumbering of a Maine bill (US-ME-01);
- the unified text behind Ecuador's archived AI bill (EC-01);
- two versions of Japan's AI Basic Plan (JP-06);
- the next stage of France's AI strategy (FR-02);
- a second edition of Brunei's guide (BN-01).

The coordinating agent, the gate and the scripts caught what the extractors and checkers did not:

- a checker that overwrote another checker's files;
- checkers that skipped the newer-version search until they were sent back to do it;
- an extractor that stored the same notice twice to raise a level;
- extractors that shortened dates because `robots.txt` blocked a source;
- six tool defects: stale browser copies, text layers of Word files and Next.js pages, `archive.py --provide`, the snapshot date, the status of compare runs, and the gate's reading of maintainers' decisions.

All were fixed before the data was merged. One rule question came out of the cycle as well: announcements had counted as official evidence. The maintainers decided that they count at most as alt-official, and two refresh runs re-graded the 56 records concerned.

## Human review

Each run drew a human sample, 24 samples in all, posted as GitHub issues. None has been answered yet, so the checkers' accuracy has so far been measured only against other agents. One or two answered samples of five records would give the first independent measure for this cycle.

## Effort

The pipeline records the tokens its subagents used per stage. The 15 runs with recorded tokens used 26.4 million tokens, about 65,000 per record. The coordinating agent's own tokens are not recorded.

| Stage | Model | Tokens | Share |
|---|---|---|---|
| extract | Claude Opus 5.5 | 20.3 million | 77% |
| check | Claude Sonnet 5.5 | 4.6 million | 17% |
| blind extract | Claude Sonnet 5.5 | 1.5 million | 6% |

Since the blind extractions on the mid-sized model agreed with the larger model on 96% of the resulting records' fields, `pipeline/roles/coordinate.md` now runs extractors in refresh and recheck runs on the mid-sized model and keeps the largest model for discover runs.

## Still open

- The 25 queued records (leads L019 to L043) and the California decision above.
- An OCR layer for image pages inside text PDFs. The covers of KR-04 to KR-07 are images and probably carry the date that would keep those records at level A.
- The human samples.

## Addendum, 19 October 2026: earlier versions in the archive

The app links each stored copy that changed to its earlier version. On 19 October such a link (UN-13's earlier secondary source) led to an empty page. Each release had uploaded only the records' current copies (and, from 1.17, the quoted evidence files) and deleted every other file from the archive dataset's main branch. Version 1.17 removed 189 files that way, mostly earlier versions; 51 of the app's 57 links to earlier versions pointed to removed files. The files had stayed on the publishing machine and in the archive's tagged revisions.

From version 1.18 on, a release publishes every copy the archiver stored of a record's sources, never deletes a file, and refuses to run when the archive holds a file the build would not list. Every file the archive ever published is in it again. `FILES.csv` in the archive and the `source_files` table mark each file `current`, `earlier version` (with the file that replaced it and when), `no longer used`, `run copy` or `register file`. The release test now checks the index and every stored file the app links.
