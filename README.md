# Every AI Policy Ever

**A register anyone can rerun with the agent they already pay for.**

Every AI Policy Ever is a pipeline of AI agents and the register of official AI safety and AI regulation instruments it maintains. Collectors search official sites, extractors write each record from a stored copy of its source with quoted evidence, a checker on a different model verifies every field, and scripts assign IDs, compute verification levels and record every change. Each step leaves a file in `runs/`, so you can rerun the pipeline with your own Claude Code or Codex subscription, or with another model, and compare your records with the published ones field by field (`AGENTS.md` sections 5 to 8). The maintainers rerun it over the full register at least once a month.

The register holds official governmental and intergovernmental instruments, from laws, executive orders and implementing rules to safety frameworks, supervisory guidance, technical standards, AI safety institute mandates, treaties and declarations. Data version <!--n:version-->1.16<!--/n--> holds <!--n:records-->400<!--/n--> records; `data/records.json` and the [releases on Hugging Face](https://huggingface.co/datasets/kelkalot/every-ai-policy-ever) say which version you have.

**Time coverage.** The register aims to hold every such instrument, but so far it is densest from 2023 on: <!--n:from_2023-->367<!--/n--> records date from 2023 or later and <!--n:before_2023-->26<!--/n--> from earlier years, the oldest from <!--n:first_year-->2017<!--/n-->. Older instruments are being added run by run. The absence of an instrument from before 2023 says nothing about whether it exists.

Every record links to its official source, says how and when it was verified, keeps a **local copy** of its sources with a SHA-256 hash, and carries its **history**: what changed, when, why and on what evidence. Anything that cannot be stored is **flagged on the record** with the reason.

**The records are an AI-based extraction.** Version 1 (340 records, 11 and 12 October 2026) was made by single AI agents in Claude Code with Claude Fable 5.1; since then the pipeline maintains it. No human has reviewed every record; a hand check of 50 randomly chosen records found no problems, and every run adds a human sample. `AGENTS.md` describes the method, its limits and how to run it.

**On Hugging Face** as *Every AI Policy Ever*:

- [Web app](https://huggingface.co/spaces/kelkalot/every-ai-policy-ever): the register in the browser, nothing to install.
- [Dataset](https://huggingface.co/datasets/kelkalot/every-ai-policy-ever): the records as Parquet tables, with the dataset card, the method and the quality reports.
- [Source documents](https://huggingface.co/datasets/kelkalot/every-ai-policy-ever-archive): the stored copies of the official sources, open to anyone with a free Hugging Face account.

## How to contribute

The register is maintained by agents that do not wait for people, so everything a person adds goes through a GitHub issue: you open it, a maintainer decides with one line, and the next pipeline run does the rest and closes the issue.

| You want to | Do this | What happens |
|---|---|---|
| **Suggest an instrument** the register lacks | Open an issue with the form [*Suggest an instrument*](https://github.com/kelkalot/every-ai-policy-ever/issues/new/choose): official URL, title, jurisdiction | A maintainer accepts or rejects it. An accepted suggestion becomes a lead for the next run, which stores the official source, writes the record from it, has it checked by a second model and merges it. The issue is closed with the new record's ID. |
| **Report news or an error** about a record | The same form, with the record ID under "Existing record" and the official source that shows the change | It goes into the next refresh run of that record, which checks the source and updates the record; the issue is closed with the run. |
| **Provide a document** the archiver cannot download | Open an issue with the form *Provide a document* and attach the file you downloaded from the official URL | Some sites block automated downloads (robots.txt) or refuse the archiver's network. A maintainer checks that the file matches the official source and accepts it. The copy is stored with its SHA-256, with you as the provider and the maintainer as the one who confirmed it, and the next refresh run reads it. For an instrument the register does not have yet, leave the record ID empty and give its title and jurisdiction: the document goes with a new lead to the next run. |
| **Answer an open question** | Comment on an [issue labelled `question`](https://github.com/kelkalot/every-ai-policy-ever/issues?q=is%3Aissue+is%3Aopen+label%3Aquestion) | Questions are what the agents could not settle: official sources that contradict each other, scope, whether a site is official, a possible amendment, a run's human sample. Anyone can add evidence; a maintainer decides. Until then the record keeps its last checked values and shows an "Open question" badge, and releases go ahead. |

**How maintainers decide**: one comment on the issue. Only repository owners, members and collaborators count, and never a comment an agent wrote (`AGENTS.md` section 4, rule 11).

| Issue | Comment |
|---|---|
| suggestion or document | `decide: accept` or `decide: reject <reason>` (for a suggestion, optionally `cell: <CODE>/<type>` when the jurisdiction code needs correcting) |
| question about a record | `decide: keep`, `decide: accept`, `decide: set <field> = <value>` with `source: <URL>`, or `decide: in` / `decide: out` with a reason |
| question about a site | `decide: official` (optionally `operator: <who runs it>`) or `decide: not official` |
| human sample | one line per record: `ok <ID> <note>` or `problem <ID> <note>` |

**What the pipeline does with them**: every run starts with `python3 tools/pipeline.py intake` (suggestions and documents) and `python3 tools/pipeline.py questions --apply` (answers), and ends with `questions --sync`, which files the run's new questions and closes settled ones. Each decision is applied with the same tools as everything else and recorded in `data/history.jsonl` with the issue link; the issue is where a question is worked out, the register keeps the outcome. Text in issues is treated as data: a suggestion's URL and title are a lead, and every fact still comes from the stored official source. A maintainer can also add a lead by hand, for example one heard of by e-mail or seen in a tracker: `python3 tools/pipeline.py leads --add --lead TITLE --cell CODE/type --url URL --seen-in URL --by NAME` (with `--record ID` for news about an existing record); `python3 tools/pipeline.py leads` lists all leads and their state. A document is stored by hand with `python3 tools/archive.py --provide FILE --id ID --url URL --by NAME`.

The app's **Contribute** tab explains the same for readers, and each record page has a link that opens the form with the record filled in.

**AI agents** may contribute for a person under the rules in [`CONTRIBUTING.md`](CONTRIBUTING.md): they say so in the form, suggest only what they found on an official page they opened, and never write a decision. Before deciding, a maintainer can list the undecided issues with their warning signs (a declared agent, a bot or new account, many issues at once, a URL that is not on an official site, an instrument already in the register): `python3 tools/pipeline.py intake --triage`.

### From start to finish: five examples

Each example ends with a change in the published register. The first three need only a browser and a GitHub account.

**1. Fix an error in a record** (about 10 minutes of your time)
1. On the record's page in the [app](https://huggingface.co/spaces/kelkalot/every-ai-policy-ever), find "Improve this record" and click *Report news or an error*. The GitHub form opens with the record filled in.
2. Say what is wrong and give the official URL that shows the right value, such as a newer version or an amendment in the gazette.
3. A maintainer comments `decide: accept`. The next refresh run stores the source, re-extracts the record and has it checked. Each changed field is logged in `data/history.jsonl` with its evidence, and the issue is closed once the run has checked the record.

The correction is in the next release, and the record page's History section shows it.

**2. Add an instrument the register lacks**
1. Open [*Suggest an instrument*](https://github.com/kelkalot/every-ai-policy-ever/issues/new/choose) with the official URL, the title and the jurisdiction code.
2. After `decide: accept` it becomes a lead (`pipeline/leads.json`). The next leads run stores the source, writes the record, checks it and merges it. The issue is closed with the new record's ID.

**3. Provide a document a site blocks**

A live case: the Texas TRAIGA record (US-TX-01) is at level C, because capitol.texas.gov forbids automated downloads of bill texts (issue #76).
1. Open the enrolled HB 149 on capitol.texas.gov in your browser and save it.
2. Open *Provide a document*, enter the record ID US-TX-01 and the URL, and attach the file.
3. A maintainer checks that it matches the official source and accepts it. The next refresh run reads it, the record's title and adoption date get official evidence, and the record returns to level A.

**4. Rerun the pipeline and check the register** (your own Claude Code or Codex subscription, about an hour)
1. Get the code and the stored documents. The archive dataset is free but needs a Hugging Face account and accepting its terms:

   ```bash
   git clone https://github.com/kelkalot/every-ai-policy-ever && cd every-ai-policy-ever
   python3 -m pip install pypdf playwright huggingface_hub && python3 -m playwright install chromium
   hf auth login
   hf download kelkalot/every-ai-policy-ever-archive --repo-type dataset --include "archive/*" --local-dir .
   python3 tools/pipeline.py menu      # what is ready now; it also checks the setup
   ```
2. Start `claude` (or `codex`) in the folder and run one item from the menu. For example:
   - `/run-pipeline refresh`, for the records most overdue for a check;
   - `/run-pipeline refresh US-04 EU-03`, for records you care about;
   - `/run-pipeline compare`, for the next definitions to quote.

   The run prints its steps, works through them and ends with a commit on a local branch `run/<run-id>`.
3. Read `runs/<run-id>/report.md`. It shows what changed, what was confirmed, how far the blind second extraction agreed with the first (the repeatability figure), and what the checker found.
4. If your run found something the register lacks, push the branch to a fork and report it with form 1, linking your report. Examples: a newer version, an amendment, a wrong date. The maintainers' next run repeats the change from their own stored copies and merges it.

A pull request with the run itself cannot be merged yet, because the documents it quotes are stored on your machine and not in git. The scripts that post to GitHub (`questions --sync`, `questions --apply`, `intake`) notice that you are not a maintainer and skip themselves.

**5. Maintainers and collaborators: a run that ends in a release**
1. `python3 tools/pipeline.py menu`; pick one item. One run per session. `new` refuses a run larger than 120 frame cells or 40 records.
2. `/run-pipeline <item>`. The run applies the pending decisions first, ends with a commit on `run/<run-id>`, opens issues for its questions and its human sample, and closes the issues it settled.
3. The run's last step is the gate (`python3 tools/gate.py`, AGENTS.md section 7.10), and it runs again on the pull request (the `gate` check). Review the report and the diff, merge only when the gate is green, and release (section 9). The release runs the gate once more, with the stored documents, and refuses to publish when it fails.

`pipeline/flow.md` shows how these paths connect.

### Contact the maintainers

For anything the issue forms do not cover, such as a question about the method, reuse of the data or a problem with the site, open a [blank issue](https://github.com/kelkalot/every-ai-policy-ever/issues/new). If you have no GitHub account, or for anything that should not be public, write to the maintainers at the AI Safety Department of SimulaMet and OsloMet: Michael A. Riegler (michael@simula.no) and Sushant Gautam (sushant@simula.no).

```
every-ai-policy-ever/
├── AGENTS.md               how the data was made, its limits, and the method for agent passes
├── index.html              the app
├── assets/                 app.css, app.js, site-config.js (where the app is hosted)
├── data/
│   ├── records.json        the database (single source of truth)
│   ├── records.js          generated: what the app loads
│   ├── records.csv         generated: for spreadsheets
│   ├── register.sqlite     generated: for SQL queries
│   └── register.xlsx       generated: Excel workbook (when openpyxl is installed)
├── archive/                local copies of sources (filled by tools/archive.py)
├── tools/
│   ├── archive.py          downloads sources, hashes them, flags failures
│   ├── build.py            regenerates records.js / .csv / .sqlite / .xlsx from records.json
│   ├── validate.py         checks records.json before a build
│   ├── export_xlsx.py      writes the Excel workbook (used by build.py)
│   ├── publish_hf.py       publishes the dataset, the source documents and the app to Hugging Face
│   ├── merge.py            merges a run's pass into records.json and writes the history
│   ├── pipeline.py         the pipeline's scripts: runs, evidence checks, questions, intake
│   └── package.py          zips everything into one shareable file
├── examples/
│   └── analysis.py         example analysis run straight from register.sqlite
├── pipeline/               the coverage frame, official sites, scope precedents, questions, leads, agent roles
├── runs/                   one folder per pipeline run: candidates, extractions, checks, report
├── docs/                   quality-check and translation-check reports
├── .github/ISSUE_TEMPLATE/ the forms for suggestions and documents
├── deploy/                 nginx.conf, Dockerfile
└── docker-compose.yml
```

## 1. View it

Pick whichever fits.

**Offline, on your own computer.** Double-click `index.html`. It opens in your browser with no server and no internet connection. Links to local copies open the files from the `archive/` folder.

**A quick local web server.**

```bash
cd every-ai-policy-ever
python3 -m http.server 8000
# open http://localhost:8000
```

**Docker (for a server).**

```bash
cd every-ai-policy-ever
docker compose up -d
# open http://<server>:8080
```

Set `REGISTER_PORT` to use another host port, for example `REGISTER_PORT=8090 docker compose up -d`. The folder is mounted read-only, so new data shows up on the next browser reload without restarting the container. To build an image that contains a frozen copy of the data and archive instead:

```bash
docker build -f deploy/Dockerfile -t ai-safety-policy-register .
docker run -d -p 8080:80 --name ai-safety-policy-register ai-safety-policy-register
```

**Any existing web server** (Apache, nginx, IIS, a university web space). Copy the folder and serve it as static files. If you use nginx, `deploy/nginx.conf` has the recommended settings (see section 5).

Search, filters and sort order are kept in the page URL, so a filtered view can be bookmarked or sent to a colleague ("Copy link to this view" next to the result count). A single record is addressed as `index.html#EU-03`.

## 2. Create the local copies

The package ships without the source documents. Run the archiver once on the machine that will host the register. It needs Python 3.8 or later and nothing else.

```bash
cd every-ai-policy-ever
python3 tools/archive.py
```

The archiver identifies itself as `AISafetyPolicyRegister-Archiver` in the User-Agent string and sends nothing about you. With the default politeness settings (one request every 2 seconds per site, 4 sites in parallel) a full run takes roughly 20 to 60 minutes.

For each record the archiver:

1. checks the site's `robots.txt`, then downloads the official URL;
2. if that is an HTML page, also downloads up to 2 PDFs it links to on the same official site, which is usually the legal text itself;
3. downloads the secondary URL as a backup;
4. saves each file under `archive/<ID>/<YYYY-MM-DD>/` and writes `SHA256SUMS` in that folder;
5. records the hash, UTC retrieval time, final URL after redirects, HTTP status, content type and server `Last-Modified` date in the record's `local_copy` block;
6. flags anything that did not work, then regenerates `records.js`, `records.csv` and `register.sqlite`;
7. rewrites `archive/needs-attention.txt`, the list of records that still need a human decision (see below).

It saves progress every 10 records, so an interrupted run (Ctrl+C) loses nothing.

`robots.txt` decides only what the archiver downloads, never what the register keeps. When it refuses a page that was stored earlier, or cannot be read (RFC 9309 then says not to crawl), the archiver does not try the page, and the stored copy stays current as it was: it is not removed, not marked stale and not flagged. Only a download that was tried and failed marks an earlier copy as possibly gone.

### What the flags mean

| Status | Meaning |
|---|---|
| `archived` | The official source was stored. |
| `archived-review` | A copy is stored but needs a human look. The site may have returned a bot-check or a JavaScript-only page, or the page may no longer mention the document's title. A source that was stored before may now be gone (the old copy is kept), or a local file may have changed since download. |
| `partial` | The official source failed; only the secondary source was stored. |
| `failed` | Nothing could be stored. The flag gives the reason: HTTP error, timeout, `robots.txt` block, TLS certificate error, or file too large. |
| `no-url` | The record has no URL to archive. |
| `not-attempted` | The archiver has not run for this record yet. |

In the app, these appear as a badge on every row, as a "Local copy" filter, and in a "Local copy" section on each record, which lists the stored files with their hashes. In the data they are in `local_copy.status` and `local_copy.flag` (and `local_status` / `local_flag` in the CSV and SQLite files).

### The decision log

After every run, and after `--verify`, the archiver rewrites `archive/needs-attention.txt`. It lists every record that is not cleanly archived, grouped by problem: nothing downloaded, only the secondary source saved, saved but needs review, no URL, or a local file that has gone missing or changed. Each entry gives the record, its URLs, the exact reason, the files that were stored, and the folder to put a manual copy in.

The archiver never contacts anyone. Whether to save a document by hand, ask the site operator for a copy, or leave the record flagged is your decision, and this file is where you make it.

### Useful options

```bash
python3 tools/archive.py --status failed,partial,archived-review   # retry only the problem records
python3 tools/archive.py --only EU-01,US-07                        # specific records
python3 tools/archive.py --browser                                 # retry failed or JavaScript-only pages in headless Chromium
python3 tools/archive.py --verify                                  # re-hash every local file; flag missing or modified ones
python3 tools/archive.py --dry-run                                 # list what would be fetched
python3 tools/archive.py --help                                    # all options (delay, timeout, PDFs per page, ...)
```

`--browser` needs Playwright: `pip install playwright && playwright install chromium`. For pages that load their content with JavaScript, it saves the rendered page and a printed PDF of it.

Some government sites block all automated downloads. Those records stay flagged and listed in `archive/needs-attention.txt`, and their official links in the app still work in a normal browser. To fill the gap, you can save the document by hand into the record's dated folder and add it to `local_copy.files` in `data/records.json`. Then run `tools/build.py` and `tools/archive.py --verify`.

## 3. Keep it current

Re-running the archiver is safe:

- an unchanged file is not stored twice; its `last_checked` time is updated. HTML pages are compared by their visible text, so pages whose scripts, session tokens or incident IDs differ on every request do not pile up new snapshots;
- a bot-check page or an empty JavaScript shell never replaces a clean earlier copy; the earlier copy is kept and the record is flagged for review;
- a changed source is stored as a new snapshot, and the record is flagged "changed", with a link to the earlier version;
- a source that has disappeared keeps its last copy, and the record is flagged for review.

To check weekly and keep a dated history in git, add a crontab entry like this one (it runs Mondays at 03:00):

```cron
0 3 * * 1  cd /srv/every-ai-policy-ever && python3 tools/archive.py >> archive/cron.log 2>&1 && python3 tools/archive.py --verify >> archive/cron.log 2>&1; git add -A && git commit -qm "archive run $(date -u +\%F)"
```

New instruments and status changes are found and checked by the agent pipeline described in `AGENTS.md` (sections 5 to 8): collectors search a coverage frame (`pipeline/frame.json`), extractors write records with quoted evidence from stored copies, a fresh checker verifies them, and `tools/pipeline.py` and `tools/merge.py` do the bookkeeping. It runs from a clone in Claude Code or Codex under your own subscription; no API keys are needed. Every change is logged in `data/history.jsonl` and summarised in `HISTORY.md` and on each record page, and each run leaves a report in `runs/<run-id>/report.md`. To start, read the pinned issue *Project status* (the maintainers' priorities, what is in progress and what is due; a GitHub Action rewrites it after every merge), then run `python3 tools/pipeline.py menu`: it lists the runs that are ready now (refresh, leads, discover, compare), each with the command that starts it, and the decisions only maintainers make. `pipeline/flow.md` shows the flow as a chart.

To edit or add records by hand, change `data/records.json`, then run `python3 tools/build.py`. The build first runs `tools/validate.py`, which checks required fields, the controlled vocabularies (instrument type, legal force, status, level, region, topics), ISO dates, related IDs and URLs. It stops on errors and summarises warnings; `python3 tools/validate.py --strict` lists every warning. A date may be shortened to `YYYY-MM` or `YYYY` when the source gives no exact day. New records start as `not-attempted` until the next archiver run.

## 4. Check the data independently

```bash
cd archive/EU-01/2026-10-12 && sha256sum -c SHA256SUMS        # hashes of the stored files
sqlite3 data/register.sqlite "SELECT id, short_title, local_status, local_flag FROM records WHERE local_status <> 'archived';"
sqlite3 data/register.sqlite "SELECT record_id, path, sha256, retrieved_at FROM archive_files WHERE record_id LIKE 'US-%';"
```

The SQLite file has the tables `records`, `topics`, `related`, `archive_files`, `archive_attempts` and `meta`.

A few stored PDFs are AES-encrypted by their publishers (some Japanese and Californian documents). `pypdf` needs the `cryptography` package to read them (`python3 -m pip install cryptography`); poppler's `pdftotext` reads them as well. A few official PDFs (Vietnamese decrees, a Turkish bill) are scans without a text layer; searching them needs OCR (for example `pdftoppm` with `tesseract`).

### Analysis without the app

The web page is only a viewer. `data/register.sqlite`, `data/records.csv` and `data/records.json` carry the same data and can be used directly in SQL, pandas, R or a spreadsheet; `archive/` holds the source documents for text analysis, with `archive_files` giving each file's path and hash. `examples/analysis.py` shows how: it answers seven questions with plain SQL (growth per year, binding share per region, topics and topic pairs, time from publication to entry into force, verification and archive coverage) and writes `examples/output/analysis.md` plus a chart if matplotlib is installed.

```bash
python3 examples/analysis.py
```

Two things to keep in mind: `date_published` can be a partial date (`YYYY-MM` or `YYYY`), so day-level calculations should require full dates, and the multi-valued CSV columns (`safety_topics`, `related_ids`, `local_files`, `local_sha256`) are joined with "; ", whereas the SQLite `topics` and `related` tables hold one row per value.

## 5. Notes for a server

- **Archived pages are untrusted content.** `deploy/nginx.conf` serves `archive/` with `Content-Security-Policy: sandbox`, so scripts inside saved pages never run on your site. If you use another web server, set the same header for `archive/`. The rest of the site gets a strict policy that blocks requests to other sites.
- **Internal access only.** Uncomment the `auth_basic` lines in `deploy/nginx.conf` and create a password file with `htpasswd -c deploy/.htpasswd <user>` (this works with `docker compose`). Alternatively, publish the container only on your internal network.
- **Public hosting.** The records, summaries and links are fine to publish. The `archive/` folder holds copies of other organisations' documents. Most government texts can be reused, but check reuse terms before serving copies publicly. To hold copies back, keep the archive local and add `location /archive/ { deny all; }` to the nginx config, or leave the folder out when you copy the site.
- **"403 Forbidden" from nginx** usually means the web server cannot read the files. Run `chmod -R a+rX .` in the register folder.
- **Size.** Expect a few hundred MB to about 2 GB for the full archive, mostly PDFs. GitHub Pages and similar hosts limit repository and file sizes, so an institutional server or object storage suits the archive better.

## 6. Scope and caveats

The scope, the verification levels (A, B, C), the records to re-check first and the known coverage gaps are explained in the app under **Method & coverage**. In short:

- In data version <!--n:version-->1.16<!--/n-->, <!--n:level_A-->352<!--/n--> records are confirmed by an official source (level A), <!--n:level_B-->25<!--/n--> by another official source (B), and <!--n:level_C-->23<!--/n--> rest on secondary sources only (C). Re-check level C records before citing them.
- Coverage is densest from 2023 on (<!--n:before_2023-->26<!--/n--> records predate 2023), and uneven across places: the coverage frame (`pipeline/frame.json`, summed up in `pipeline/coverage.md`) records which places the pipeline has searched. Supervisory authorities and standards bodies were added to the scope in October 2026 and are not yet searched (issue #30 plans the pilot).
- The register does not translate instruments. About a third of the records rest on a text that is not in English; their summaries were written in English by an AI agent from the original, and their English titles are the agent's renderings unless the record's `english_version` names an English text of the issuer or a government translation. For point-by-point work use the original or that translation. A translation check of 58 such records (`docs/translation-check-2026-10-14.md`) found the titles accurate, 73 percent of specific summary claims accurate and 10 percent overstated, understated or mistranslated, and six records with an error that changes the legal meaning, which are being corrected.
- Statuses are as of each record's `verification.verified_on`. The archiver detects changes to the source pages and queues the record for a refresh run, which re-checks its status; `meta.snapshot_date` changes only after a recheck of every record.

## 7. Share it as one file

```bash
python3 tools/package.py                # dist/every-ai-policy-ever_<snapshot>.zip, with all source documents
python3 tools/package.py --no-archive   # a few MB: app and data only
```

The git repository holds the code and the text data (`records.json`, `records.js`, `records.csv`); the source documents in `archive/` and the generated binaries (`register.sqlite`, `register.xlsx`) are not committed and travel in this package instead. The packager validates and rebuilds the data, then zips the app, the data in every form (JSON, CSV, SQLite, Excel), the local copies with their `SHA256SUMS`, the tools and the analysis example into one folder. Two files sit at its top: `PACKAGE.txt` explains what is inside and how to open it, and `MANIFEST-SHA256.txt` lists a hash for every file, so the recipient can run `shasum -a 256 -c MANIFEST-SHA256.txt` (Linux: `sha256sum -c`). A `.sha256` file next to the zip holds the hash of the zip itself. The full package is a few hundred MB, mostly PDFs; the `--no-archive` variant fits in an e-mail.

## 8. Excel workbook

`data/register.xlsx` is written by `tools/build.py` whenever the `openpyxl` package is installed (`python3 -m pip install openpyxl`; `python3 tools/export_xlsx.py` writes it on its own). It has six sheets: **About** (what the file is, a glossary of every column), **Records** (the 33 columns of `records.csv` with clickable URLs, filters and a frozen header), **Topics** and **Related** (one row per topic and per link, ready for pivot tables), **Local copies** (one row per stored file with hash and retrieval time) and **Needs attention** (the records that are not cleanly archived). It contains no formulas, so every viewer shows the same values; dates are ISO text because some are partial.

## 9. Publish to Hugging Face

```bash
python3 -m pip install huggingface_hub pyarrow
hf auth login                              # with a token that has write access
python3 tools/publish_hf.py                # build dist/hf/ and stop, to review the cards and tables
python3 tools/publish_hf.py --push         # build and upload
```

The tool builds three repositories from `data/records.json`:

- **`kelkalot/every-ai-policy-ever`** (dataset): the records, topics, related links and a manifest of every stored source file as Parquet tables, plus the full JSON, CSV and Excel files, `AGENTS.md` and the quality reports. The dataset card is generated with the current counts.
- **`kelkalot/every-ai-policy-ever-archive`** (dataset, gated with automatic approval): the stored copies of the official sources with their `SHA256SUMS`. A Hugging Face account is needed to download them, which keeps crawlers out. Copies of third-party pages (law-firm alerts, newspapers, NGO and think-tank pages, listed in `THIRD_PARTY_HOSTS` in the tool) are left out; their URLs and hashes stay in the manifest.
- **`kelkalot/every-ai-policy-ever`** (static Space): the web app. Its "Local copy" links point at the archive dataset.

`--private` creates the repositories as private, for a review before they go public.

A new version is published as a release, from the main branch on the machine that holds `archive/`. Main accepts changes only through pull requests that pass the `gate` check (a ruleset, AGENTS.md section 7.10), so the version goes through one as well: bump `meta.version` in `data/records.json` on a branch, run `python3 tools/build.py`, open a pull request, and merge it when the gate is green. Then, on main:

```bash
python3 tools/publish_hf.py --release --dry-run    # every check, no upload
python3 tools/publish_hf.py --release              # upload all three repositories and tag the version
```

First the release runs the gate (`tools/gate.py`, AGENTS.md section 7.10) on every change since the last release tag, with the stored documents, and stops if it fails. Then, before uploading, it checks that main is clean and pushed, that `meta.version` is higher than the published version and not yet tagged, that no record published before is missing (records are never deleted), that the history and the stored files are intact, that the built archive holds no live access tokens, and that the Hugging Face token can write. It adds a "Changes in this version" section to the dataset card from the history events since the last release, and tags the version (`v1.7`, ...) on the dataset, the archive, the Space and GitHub, so a citation can name a fixed version.

The rhythm: run the archiver weekly to notice changed sources; rerun the pipeline over the full register at least once a month (recheck runs of at most 40 records each, to stay within usage limits), with refresh runs from the queue in between, a discover run per group of countries quarterly, and compare runs from the comparison queue (AGENTS.md sections 5 to 7); after a human has reviewed and merged a run's branch, bump `meta.version` in a pull request (minor for added records, patch for corrections) and release. Use a fine-grained Hugging Face token with write access to these three repositories only, passed as `HF_TOKEN` for the release command. The archive dataset only grows; a history squash (`--squash-archive`) is for incidents such as a leaked credential.

## 10. License and citation

The code, the web app and the records, summaries and notes are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); see `LICENSE`. The stored source documents remain under their publishers' terms.

<!-- build:bibtex -->
```bibtex
@dataset{riegler_gautam_2026_every_ai_policy_ever,
  title     = {Every AI Policy Ever: a register of official AI safety and AI regulation instruments},
  author    = {Riegler, Michael and Gautam, Sushant},
  year      = {2026},
  version   = {1.16},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/datasets/kelkalot/every-ai-policy-ever},
  note      = {AI-assisted extraction, snapshot 2026-10-12}
}
```
<!-- /build:bibtex -->

Say in your own text that the register is an AI-assisted extraction, and name the verification level of the records you rely on.

