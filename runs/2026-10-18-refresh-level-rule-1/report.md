# Run 2026-10-18-refresh-level-rule-1

<!-- coordinator: one paragraph here on what a human should look at first -->
First refresh under the new level rule (an announcement counts at most as alt-official; A means the instrument's own text or an official register confirms the record), on 29 records whose title, date or status rested on an announcement, plus ASEAN-01 and JP-06. 13 stay at A and 16 fall to B. Records stay at A where the instrument's own text was stored and became official_url (ASEAN-01, ASEAN-02, CN-17, IE-01, MY-03, ES-03, US-09) or where the date now has the precision the text gives, with the exact day in the notes (CA-07 2026, CN-17 2026-09, MY-03 2026, US-16 2025-07, US-22 2026-03). Records fall to B where no text of the instrument exists or could be stored: the institute mandates announced by press release (AUS-07, CA-05, GB-07, NO-03, SG-03), SG-02, SG-04, SG-08 (its version 1.0 date rests on the launch release), CH-01, DK-02 (the bill text on ft.dk could not be stored), US-03, US-25 (congress.gov refuses the archiver), UN-02, IN-01, MY-01 (the guidelines carry no date) and HK-01. JP-06's two dates are two versions: the first AI Basic Plan was decided on 23 December 2025 and the second on 14 July 2026, so date_published and date_last_updated now say so. INT-11's date is now the one the mission statement gives itself, 21 November 2024. Look first at the two judgment calls the checkers flagged: the ASEAN ministers' joint media statements counted as their formal record of the decision (official), and the Council of Ministers' referencia for ES-03.

Type: refresh. Scope: ids:ASEAN-01,ASEAN-02,INT-11,OECD-02,UN-02,AUS-07,CA-05,CA-07,CN-17,DK-02,IN-01,IE-01,JP-06,MY-01,MY-03,NO-03,SG-02,SG-03,SG-04,SG-08,ES-03,CH-01,GB-07,US-03,US-09,US-16,US-22,US-25,HK-01. Started 2026-10-18; report written 2026-10-18.

| Stage | Tool | Model | Date |
|---|---|---|---|
| collect | - | - | - |
| extract | Claude Code | claude-opus-5-5 | 2026-10-18 |
| blind | Claude Code | claude-sonnet-5-5 | 2026-10-18 |
| check | Claude Code | claude-sonnet-5-5 | 2026-10-18 |

## Summary

- Candidates: 29 (active 29)
- Added: 0; fields changed: 67 in 28 record(s); re-verified without change: 1
- Not added: 0; need a human: 0; not ready: 0
- Repeatability: 80% field agreement between blind double extractions (5 pair(s)); 98% agreement on the resulting records (53 field values; in a refresh run the first figure counts only fields that an extraction changed)

## Added

None.

## Changed

- **ASEAN-01** official_url: https://asean.org/book/asean-guide-on-ai-governance-and-eth… → https://asean.org/wp-content/uploads/2024/02/ASEAN-Guide-on… (the asean.org /book/ page (a catalogue entry about the guide) -> the guide's own PDF on asean.org, stored in this run (rule 7c))
- **ASEAN-01** secondary_url: - → https://asean.org/book/asean-guide-on-ai-governance-and-eth… (null -> the asean.org /book/ publication page, which gives the ASEAN Secretariat as author and publisher)
- **ASEAN-02** official_url: https://asean.org/book/expanded-asean-guide-on-ai-governanc… → https://asean.org/wp-content/uploads/2025/01/Expanded-ASEAN… (the asean.org /book/ page (a catalogue entry about the guide) -> the guide's own PDF on asean.org, stored in this run (rule 7c))
- **ASEAN-02** secondary_url: - → https://asean.org/book/expanded-asean-guide-on-ai-governanc… (null -> the asean.org /book/ publication page, which gives the ASEAN Secretariat as author and publisher)
- **INT-11** date_published: 2024-11-20 → 2024-11-21 (2024-11-20 -> 2024-11-21: the mission statement dates itself ('gathered today in San Francisco on November 21, 2024 to launch the International Network'); 20 November 2024 is the release date of the US fact sheet, an announcement about it. A statement's date is taken from the document itself (extract.md step 1), and the notes already give both days.)
- **UN-02** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **AUS-07** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **CA-05** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **CA-07** date_published: 2026-06-04 → 2026 (2026-06-04 -> 2026: the strategy's own text (page and PDF) gives only the year 2026; the launch day, 4 June 2026, is given only by announcements (the Prime Minister's and ISED's news releases). Rule 7b: write the date at the precision of the instrument's own text and put the day, with its source, in the notes.)
- **CA-07** notes: Launched by Prime Minister Mark Carney on 4 June 2026; the … → Launched by Prime Minister Mark Carney on 4 June 2026 (Prim… (first sentence: the launch day now names its sources (the Prime Minister's news release of 4 June 2026 and ISED's of 5 June 2026); the rest is unchanged)
- **CA-07** scope_note: Mainly a strategy for AI adoption, skills, sovereign infras… → Mainly an adoption and sovereignty strategy, with a first p… (pipeline run 2026-10-18-refresh-level-rule-1 (refresh), candidate CA-07)
- **CN-17** issuing_body: National Cybersecurity Standardization Technical Committee … → National Technical Committee 260 on Cybersecurity of the St… (the issuer's own English name as the framework's English text gives it ('National Technical Committee 260 on Cybersecurity of the Standardization Administration of China'), with the CAC's guiding role kept)
- **CN-17** date_published: 2026-09-14 → 2026-09 (the framework's own text gives only 2026年9月 on its cover; the day (14 Sept 2026) comes from the release notices, which are announcements, so it moves to the notes (rule 7b))
- **CN-17** official_url: https://www.tc260.org.cn/tc260/xwdt1/202609/e879077a3caa472… → https://www.tc260.org.cn/tc260/xwdt1/202609/e879077a3caa472… (the record pointed at TC260's release notice, an announcement that attaches the framework; the framework PDF itself is now stored and becomes official_url (rule 7c))
- **CN-17** notes: Released on 14 Sept 2026 at the opening ceremony of the 202… → TC260 released it on 14 Sept 2026, the day both its own rel… (first sentence now gives the release day with its sources and says the framework is dated September 2026)
- **DK-02** title: Bill amending the Copyright Act (introduction of performanc… → Bill amending the Copyright Act (protection of personal cha… (the bill introduced on 8 Oct 2026 has a different title from the 2025 notified draft; the English title now renders the Folketing's title of L 49 (no official English text of the bill is known))
- **DK-02** original_title: Forslag til lov om ændring af ophavsretsloven (værn mod dig… → Forslag til lov om ændring af lov om ophavsret. (Beskyttels… (replaced the unverified wording with the bill's title verbatim from the Folketing's case record (the record's closing full stop dropped))
- **DK-02** official_identifier: TRIS notification 2025/0654/DK → L 49 (2026-27) (the citable number of a bill is its Folketing number, L 49; the TRIS number of the 2025 draft stays in the notes)
- **DK-02** notes: Implements the political agreement of 26 June 2025 between … → Implements the political agreement of 26 June 2025 between … (gives the notified draft's English title, which no longer serves as the record's title, and the bill number; drops the remark that the English title is that of the notified draft)
- **DK-02** scope_note: Copyright-law bill whose operative effect is a right agains… → A copyright-law bill rather than an AI-specific law; includ… (the published scope_note was a reviewer's remark (it cites 'section 10' and says 'A scope_note is advisable'); rewritten as a public statement of why the bill is borderline and included)
- **DK-02** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **IN-01** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **IE-01** official_url: https://aioffice.gov.ie/news-and-updates/ai-office-of-irela… → https://www.irishstatutebook.ie/eli/2026/act/31/enacted/en/… (the record pointed at the AI Office's news item, an announcement; the Act as enacted (Irish Statute Book, ELI) is now stored and becomes official_url (rule 7c))
- **JP-06** date_published: 2026-07-14 → 2025-12-23 (the plan's own text says the Cabinet decided the first AI Basic Plan on 23 Dec 2025; the text of 14 Jul 2026 is its second term (第Ⅱ期計画), a new version of the same statutory plan, so 2025-12-23 is the adoption date)
- **JP-06** date_last_updated: - → 2026-07-14 (14 Jul 2026, the Cabinet decision of the current second-term version (cover of the plan))
- **JP-06** notes: The first AI Basic Plan was decided by the Cabinet on 23 De… → The Cabinet first decided the AI Basic Plan on 23 Dec 2025.… (first two sentences describe the two versions as one plan; the rest unchanged)
- **JP-06** scope_note: Statutory national AI plan whose main content is promotion … → Statutory national AI plan whose main content is promoting … (the published scope_note was a reviewer's remark (it names the 'include-and-flag rule' and says 'the record has none'); rewritten as a public statement of why the plan is borderline and included)
- **MY-01** notes: Deputy Prime Minister Fadillah Yusof launched the guideline… → MOSTI's press release of 20 Sep 2024 says Deputy Prime Mini… (first sentence now names the press release as the source of the day)
- **MY-01** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **MY-03** date_published: 2026-07-28 → 2026 (the plan's own text gives only the year (its 2026 copyright); the day (28 Jul 2026) rests on the press statement, an announcement, so it moves to the notes (rule 7b))
- **MY-03** official_url: https://ai.gov.my/ → https://strapi.naio.okie.my/uploads/AI_Nation_2030_National… (the record pointed at AI Malaysia's homepage, which links the plan but is not its text; the English PDF, the plan's own text, becomes official_url (rule 7c))
- **MY-03** secondary_url: https://strapi.naio.okie.my/uploads/AI_Nation_2030_National… → https://strapi.naio.okie.my/uploads/28072026_SIARAN_MEDIA_A… (the Ministry of Digital's press statement of 28 Jul 2026, which gives the day the plan was introduced and backs the notes on the launch, replaces the English PDF, now the official_url)
- **MY-03** notes: The government introduced the plan on 28 Jul 2026 at the la… → The Ministry of Digital's press statement of 28 Jul 2026 sa… (first sentence now names the press statement as the source of the day)
- **MY-03** scope_note: - → A national AI action plan mainly about adoption and growth,… (pipeline run 2026-10-18-refresh-level-rule-1 (refresh), candidate MY-03)
- **NO-03** notes: The post of director was advertised on 11 Feb 2026, the app… → The ministry's allocation letter for 2026 to Digdir, dated … (the allocation letter of 6 Feb 2026, stored in this run, added: KI Norge as a main priority of Digdir for 2026, the statutory AI sandbox placed in it and run with Nkom and Datatilsynet, the national AI guidance portal, and the funding (NOK 10 million for KI Norge, NOK 4.8 million for the sandbox))
- **NO-03** scope_note: An AI adoption and guidance body rather than an AI safety i… → Existing scope_note kept: an institutional mandate whose ow… (pipeline run 2026-10-18-refresh-level-rule-1 (refresh), candidate NO-03)
- **NO-03** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **SG-02** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **SG-03** summary: Designates the Digital Trust Centre, a national centre host… → Designates the Digital Trust Centre, which IMDA had appoint… (rewritten from the factsheet's body, which the text layer now includes: the AISI's tasks as the designation states them, its four initial research areas and the Centre's set-up in June 2022; IMDA's role and the Centre's technical role stay from the AISI page; the current work moved to the notes)
- **SG-03** safety_topics: + research priorities (research priorities added: the factsheet sets the AISI's initial research areas)
- **SG-03** notes: IMDA's factsheet announcing the designation carries the dat… → IMDA's factsheet announcing the designation carries the dat… (the Centre's set-up funding and early research focus, the 2024 discussions with the US and UK AISIs and the link to expanding AI Verify added from the factsheet; the current testing and societal-impact work kept from the AISI page)
- **SG-03** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **SG-04** notes: IMDA and the AI Verify Foundation released a proposed frame… → IMDA and the AI Verify Foundation released a proposed frame… (the factsheet's body, now in the text layer, gives the more than 70 responses and the kind of respondents, and that the playbook for small states is developed with Rwanda; added. The 2023 Discussion Paper and the guidelines to follow rest on the framework PDF, stored in this run)
- **SG-04** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **SG-08** official_url: https://www.mddi.gov.sg/newsroom/singapore-launches-new-mod… → https://www.imda.gov.sg/-/media/imda/files/about/emerging-t… (the record's official_url was MDDI's press release, an announcement; the framework's own text is published on imda.gov.sg and already stored as the record's secondary source, so it becomes official_url (rule 7c))
- **SG-08** secondary_url: https://www.imda.gov.sg/-/media/imda/files/about/emerging-t… → https://www.mddi.gov.sg/newsroom/singapore-launches-new-mod… (the press release, previously official_url, becomes the secondary source)
- **SG-08** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **ES-03** official_url: https://www.lamoncloa.gob.es/consejodeministros/referencias… → https://www.congreso.es/public_oficiales/L15/CONG/BOCG/A/BO… (the bill's own text, published in the BOCG and stored in this run, replaces the referencia of 11 March 2025, which recorded the earlier anteproyecto (rule 7c: official_url points at the instrument))
- **ES-03** secondary_url: - → https://www.lamoncloa.gob.es/consejodeministros/referencias… (the referencia of 11 March 2025, previously official_url, becomes the secondary source; it gives date_published)
- **CH-01** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **GB-07** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **US-03** official_url: https://bidenwhitehouse.archives.gov/briefing-room/statemen… → https://bidenwhitehouse.archives.gov/wp-content/uploads/202… (the record pointed at the White House fact sheet, an announcement; the commitments' own text (the PDF linked from it, stored as document-1 on 11 Oct 2026) is published, so it becomes official_url (extract.md rule 7c))
- **US-03** secondary_url: - → https://bidenwhitehouse.archives.gov/briefing-room/statemen… (the fact sheet, which gives the date and the seven companies, moves here from official_url)
- **US-03** scope_note: Commitments made by AI companies, which the White House bro… → Existing scope_note kept: company commitments brokered and … (pipeline run 2026-10-18-refresh-level-rule-1 (refresh), candidate US-03)
- **US-03** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **US-09** official_url: https://bidenwhitehouse.archives.gov/briefing-room/statemen… → https://bidenwhitehouse.archives.gov/briefing-room/presiden… (the record pointed at the White House fact sheet, an announcement; the memorandum's own text, linked from it and stored in this run, becomes official_url (extract.md rule 7c))
- **US-09** secondary_url: - → https://bidenwhitehouse.archives.gov/briefing-room/statemen… (the fact sheet moves here from official_url)
- **US-09** summary: The first national security memorandum on AI. It directs th… → Presidential memorandum on AI and national security, with a… (rewritten from the memorandum's own text instead of the fact sheet: its three objectives, the AI Safety Institute's role in voluntary pre- and post-deployment testing of frontier models (cyber, biological and chemical weapons), the classified annex and the Framework's prohibited and high-impact uses; the fact sheet's 'top-tier intelligence priority' is not in the public text and moved to the notes with its source)
- **US-09** notes: Issued 24 Oct 2024 together with the Framework to Advance A… → Signed by President Biden on 24 Oct 2024. It fulfils the di… (rewritten from the memorandum: signature date, subsection 4.8 of EO 14110, approval and periodic review of the Framework by the NSC Deputies Committee; the fact sheet's intelligence-priority claim set beside what the public text directs)
- **US-16** date_published: 2025-07-23 → 2025-07 (the plan's own text gives only 'JULY 2025'; the day, 23 July 2025, rests on the White House announcement, so the date is written at the month's precision and the day stays in the notes with its source (extract.md rule 7b))
- **US-16** notes: Released by the White House on 23 July 2025 under Executive… → The White House announced the plan's release on 23 July 202… (first sentence reworded so that the release day names its source, the White House announcement of 23 July 2025; the rest is unchanged)
- **US-22** date_published: 2026-03-20 → 2026-03 (the document's own text gives only 'MARCH 2026'; the day, 20 March 2026, rests on the White House release of that day, so the date is written at the month's precision and the day stays in the notes with its source (extract.md rule 7b))
- **US-22** notes: Released on 20 March 2026; the document itself is dated Mar… → The White House announced the framework on 20 March 2026; t… (first sentence reworded so that the day names its source, the White House release of 20 March 2026; the rest is unchanged)
- **US-25** official_url: https://obernolte.house.gov/media/press-releases/obernolte-… → https://obernolte.house.gov/sites/evo-subsites/obernolte.ho… (the record pointed at the sponsors' press release, an announcement; the bill's own text, linked from it and stored as document-1 on 11 Oct 2026, becomes official_url (extract.md rule 7c))
- **US-25** secondary_url: https://obernolte.house.gov/sites/evo-subsites/obernolte.ho… → https://obernolte.house.gov/media/press-releases/obernolte-… (the press release, which gives the introduction date and the co-sponsors, replaces the section-by-section summary here; the summary remains among the record's stored files)
- **US-25** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **HK-01** verification.level: A → B (level computed from the evidence by tools/pipeline.py)

## Re-verified without change

OECD-02

## Needs a human



None.

## Merged with an open question

The run's checked corrections are merged; these points about values it left as published are open questions (GitHub issues, `pipeline.py questions --sync`).

- IN-01: checker: All stored evidence is an announcement, labelled alt-official, so level B is right. The one open point is date_published: the day is real but its file belongs to another run and is not linked to this record. Attach the PIB release to the record (extra_urls) so the date has accepted evidence. Search found no establishing order; a secondary report says a consultation paper is due, not a newer version.; date_published is unsupported and the checker gave no evidence-backed fix; the checker found something possibly newer: {'url': 'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2097709', 'reason': 'PIB release of 30 Jan 2025 (stored in run 2026-10-18-recheck-south-asia-1, not linked to IN-01); it gives the announcement date for date_published.'}
- US-03: checker: Only the status is a problem and the run does not change it, so the run's corrections (official_url now the commitments text, fact sheet as secondary, verification note) can be merged while the status question stays with the maintainers (issue #134). Title wording, date and the seven companies rest on the fact sheet, an announcement, correctly labelled alt-official (level B). No official source found that withdraws or replaces the commitments.; status is unsupported and the checker gave no evidence-backed fix

## Not added

None.

## Repeatability

Blind second extraction of 5 candidate(s) (AGENTS.md section 7.4).

| Field | Compared | Agree |
|---|---:|---:|
| decision | 5 | 5 |
| issuing_body | 1 | 0 |
| date_published | 4 | 4 |

## Human sample

Check these records against their stored sources, then log the result, for example:

    python3 tools/pipeline.py log-human --run 2026-10-18-refresh-level-rule-1 --id CA-05 --result ok --note "..."

- [ ] CA-05 CAISI
- [ ] CN-17 AI Safety Governance Framework 3.0
- [ ] HK-01 Hong Kong Ethical AI Framework
- [ ] SG-08 Singapore MGF for Agentic AI
- [ ] UN-02 UNGA resolution on safe, secure and trustworthy AI

## Hosts to review

Quotes from these hosts counted as secondary because the host is neither a government domain nor listed in `pipeline/official-sites.json`. If the issuing body runs the host, or uses it as its own channel, record it with `python3 tools/pipeline.py hosts --add HOST --code CODE --status official --by NAME --operator ... --evidence-url ...`, and run `evidence` again.

- oda.ft.dk: DK-02

## Leads and open questions

- DK-02: The bill text as introduced (https://www.ft.dk/ripdf/samling/20261/lovforslag/l49/20261_l49_som_fremsat.pdf) could not be stored: ft.dk answered HTTP 403 and the browser retry timed out. A person could provide it with the 'Provide a document' form. It would give official evidence for the date of introduction (the record would then compute to level A), the provisions as introduced (the summary now rests on the press release) and the proposed entry-into-force date, and it would become official_url.
- DK-02: oda.ft.dk, the Folketing's open-data service, is not in pipeline/official-sites.json, so the quotes from the Folketing's case record for L 49 count as secondary. If a maintainer records oda.ft.dk (and ft.dk) as official for DK, the title, original_title, identifier and status quotes count as official; the date of introduction would still need the bill text.
- HK-01: date_published (2021) rests only on a speech of 30 Oct 2025; no stored file of the framework itself, and no official record, dates its first version. The framework's first version or an official notice of its issue would let the date rest on the instrument's own text.
- IN-01: date_published (2025-01-30) has no evidence stored in this run: the PIB release of 30 Jan 2025 (https://www.pib.gov.in/PressReleasePage.aspx?PRID=2097709) could not be reached (DNS failure); it is stored from run 2026-10-18-recheck-south-asia-1 at archive/_runs/2026-10-18-recheck-south-asia-1/IN-01/extra-7e03fe7de9/2026-10-18/official.html. The stored PSA copy of the IndiaAI article is dated 31 Jan 2025.
- IN-01: The official_url (IndiaAI article on indiaai.gov.in) has never been stored from the archiver's network, and the article itself says its information was procured through secondary sources. The PIB release of 30 Jan 2025 is MeitY's own announcement and could serve as official_url; both are announcements, so the level stays B either way.
- MY-03: The plan PDFs AI Malaysia now serves are named as a version of 18 Aug 2026, three weeks after the plan was introduced on 28 Jul 2026, and the plan states no date. Whether the 18 Aug version revised the text introduced on 28 Jul (which would make 2026-08-18 a date_last_updated) is not shown by any stored file.
- NO-03: NO-03 rests on the opening press release of 12 Jun 2026 (level B). The instrument that set KI Norge up is the ministry's allocation letter for 2026 to Digdir (ref. 25/2333, 6 Feb 2026), now stored; it is a general allocation letter in which KI Norge is one priority. Should the record be anchored on it (official_url, date_published 2026-02-06, a title such as 'Establishment of KI Norge'), which would make it level A, or stay on the opening as now?
- UN-02: The resolution's own text cannot be stored by the archiver (Digital Library bot-check, documents.un.org robots.txt, press.un.org Client Challenge), and the stored copy of the General Assembly's list of resolutions of the 78th session shows only 78/319 to 78/331. The record stays at level B, and its summary and topics rest on the operative text that UN News quotes, until a person provides the resolution (AGENTS.md section 7.8, 'Provide a document').
- US-03: Status 'Superseded' is not shown by any stored file of this record or by the stored text of US-27; issue #134 asks a maintainer to decide. Left as published.
- US-09: The companion Framework to Advance AI Governance and Risk Management in National Security is not stored (its ai.gov URL redirected to the si.gov home page on 17 Oct 2026). A person could provide the Framework PDF with the 'Provide a document' form.
- US-25: official_identifier stays null: the bill text leaves the number blank ('H. R. __'). Third-party trackers list the bill as H.R. 9925, introduced 23 Jul 2026 and referred to the Committee on Energy and Commerce and the Committee on Science, Space, and Technology. The congress.gov page (https://www.congress.gov/bill/119th-congress/house-bill/9925/all-info) refused the archiver on 18 Oct 2026; a person could provide it with the 'Provide a document' form, which would also give an official date for date_published and lift the record to level A.
- US-25: The sixth sponsor's name: the press release writes 'Subramanyan', the record 'Subramanyam'; no stored official source settles the spelling.
