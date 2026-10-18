# Run 2026-10-18-refresh-level-rule-2

<!-- coordinator: one paragraph here on what a human should look at first -->
Second refresh under the new level rule, on the other 29 records whose title, date or status rested on an announcement, plus GB-10 and NL-01 after the host decisions. 14 stay at A, 15 fall to B, GB-10 rises from C to A and NL-01 stays at B. Records stay at A where the legislature's own record now confirms the statute (the Senate and Assembly weekly histories for US-CA-01, US-CA-02, US-CA-06, US-CA-07, US-CA-08 and US-CA-14; US-CA-07 and US-CA-08 now carry their chapter numbers, and US-CA-02 and US-CA-06 their 2026 amending chapters), where the instrument's text became official_url (IS-01, JP-12, KH-01), or where the date now has the precision the text gives, with the exact day in the notes (IS-01 2025-07, G20-01 2025-11, SI-02 2026, CN-19 2026-09, JP-12 2026-03). GB-10 rests on the UK Parliament Bills API, recorded as official in #125. Records fall to B where the record rests on a signing release or news item (US-IL-02, US-IL-03, US-HI-01, UA-01, SA-04, LV-02) or a brochure (FR-02, whose Superseded status rests on the announcement of the strategy's second phase), and where the day comes only from a notice and the stored text gives no date: KR-04 to KR-07 (their covers are images, which textify does not OCR inside a text PDF), HK-02 (the stored text is version 1.1 of December 2025), JM-01 and BN-01. KR-08 is dated 2026 from its cover but falls to B because its status rests on NIA's notice. Look first at KH-01 (the draft strategy PDF on OECD.AI's storage counted as the issuer's own text, so it stays at A), BN-01 (AITI's page lists a second edition that could not be read, #188), US-CA-02 (SB 1000, Chapter 861 of 30 Sep 2026, amends the Act and its text is not stored, #187) and KR-05 (issuer and last-updated date unsupported, #184).

Type: refresh. Scope: ids:HK-02,US-CA-01,US-CA-02,US-CA-06,US-CA-07,US-CA-08,US-IL-02,IS-01,UA-01,G20-01,ID-02,US-IL-03,SA-04,SI-02,BG-01,LV-02,KR-04,KR-05,KR-06,KR-07,KR-08,BN-01,KH-01,US-HI-01,JM-01,CN-19,JP-12,US-CA-14,FR-02,GB-10,NL-01. Started 2026-10-18; report written 2026-10-18.

| Stage | Tool | Model | Date |
|---|---|---|---|
| collect | - | - | - |
| extract | Claude Code | claude-opus-5-5 | 2026-10-18 |
| blind | Claude Code | claude-sonnet-5-5 | 2026-10-18 |
| check | Claude Code | claude-sonnet-5-5 | 2026-10-18 |

## Summary

- Candidates: 31 (active 31)
- Added: 0; fields changed: 59 in 30 record(s); re-verified without change: 1
- Not added: 0; need a human: 0; not ready: 0
- Repeatability: 0% field agreement between blind double extractions (5 pair(s)); 98% agreement on the resulting records (58 field values; in a refresh run the first figure counts only fields that an extraction changed)

## Added

None.

## Changed

- **HK-02** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **US-CA-01** safety_topics: + general-purpose / frontier AI (added 'general-purpose / frontier AI' (the record had one topic; the vocabulary needs two to six): the law's duties fall on developers of generative AI systems and services and concern the data used to train them)
- **US-CA-01** notes: Signed on 28 Sep 2024 as Chapter 817, Statutes of 2024; the… → Approved by the Governor and chaptered on 28 Sep 2024 as Ch… (first sentence now gives the approval and chaptering from the Assembly's record and the Civil Code title the act adds; the rest is unchanged)
- **US-CA-02** date_last_updated: 2025-10-13 → 2026-09-30 (2025-10-13 -> 2026-09-30: AB 2713, which amends Section 22757.3.1 of the Act, was approved by the Governor and chaptered on 30 Sep 2026 (Chapter 856, Statutes of 2026), according to the Assembly's record)
- **US-CA-02** official_identifier: Chapter 291, Statutes of 2024 (Senate Bill 942); amended by… → Chapter 291, Statutes of 2024 (Senate Bill 942); amended by… (adds Chapter 856, Statutes of 2026 (AB 2713) to the amending acts)
- **US-CA-02** notes: Signed on 19 Sep 2024 as Chapter 291, Statutes of 2024, and… → Signed on 19 Sep 2024 as Chapter 291, Statutes of 2024, and… (last sentence: AB 2713 is no longer a proposal but an enacted amendment; it now gives the chapter, the approval date, its subject title and the section it amends)
- **US-CA-06** date_last_updated: - → 2026-09-10 (null -> 2026-09-10: the Senate's record shows that SB 867 (Chapter 189) amends Section 22601 and SB 1119 (Chapter 190) amends Section 22602 of the Business and Professions Code, both approved on 10 Sep 2026, and that SB 243 added Chapter 22.6 commencing with Section 22601; the earlier recheck had no stored file showing which sections SB 1119 amends)
- **US-CA-06** official_identifier: Chapter 677, Statutes of 2025 (Senate Bill 243) → Chapter 677, Statutes of 2025 (Senate Bill 243); amended by… (adds the two amending chapters of 2026 (SB 867, SB 1119))
- **US-CA-06** notes: Passed the Assembly 59-1 on 10 Sep 2025 and the Senate 33-3… → Passed the Assembly 59-1 on 10 Sep 2025 and the Senate 33-3… (adds the Code chapter SB 243 adds and replaces the last sentence (based on a release no longer among the stored sources) with the two amending acts from the Senate's record)
- **US-CA-07** title: Independent Verification Organizations for AI Systems (SB 8… → Independent Verification Organizations (SB 813) and Artific… (the agent's rendering ('Independent Verification Organizations for AI Systems (SB 813), with companion AI Auditor Registry law (AB 1405)') replaced by the two bills' subject titles in the legislature's records, as for the register's other California bills (US-CA-12 'Toys: Companion Chatbots (SB 867)'))
- **US-CA-07** official_identifier: California Senate Bill 813 and Assembly Bill 1405; Governme… → Chapter 179, Statutes of 2026 (Senate Bill 813); Chapter 17… (bill numbers and Code sections replaced by the citable chapter numbers from the legislature's records (Chapters 179 and 178, Statutes of 2026); the Code sections stay in the notes)
- **US-CA-07** notes: Both signed 9 Sep 2026. EO N-9-26 of 18 Sep 2026 (US-CA-09)… → Both approved by the Governor on 9 Sep 2026: SB 813 as Chap… (first sentence now gives the approval date, the chapters and the Government Code chapters each act adds)
- **US-CA-08** official_identifier: California Senate Bill 1119 (2025-2026 Regular Session) → Chapter 190, Statutes of 2026 (Senate Bill 1119) ('California Senate Bill 1119 (2025-2026 Regular Session)' -> the citable chapter from the Senate's record, Chapter 190, Statutes of 2026)
- **US-CA-08** notes: Passed the Legislature on 31 Aug 2026 (Senate 39-0, Assembl… → Passed the Senate 39-0 on 19 May 2026 and, as amended, the … (votes corrected to the Senate's record (Senate 39-0 on 19 May 2026, Assembly 69-4 and Senate concurrence 39-0 on 31 Aug 2026; the release's 64-4 kept as a discrepancy); chapter, approval date and the Code sections the act amends and adds added; the rest unchanged)
- **US-IL-02** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **IS-01** date_published: 2025-07-01 → 2025-07 (2025-07-01 -> 2025-07: the plan's own text (both editions' imprints) gives only 'July 2025' / 'Júlí 2025'; the day comes from the government's news items, which are announcements, and the notes already give both days (rule 7b))
- **IS-01** official_url: https://www.stjornarradid.is/frettir/grein/2025-07-01-Icela… → https://www.stjornarradid.is/library/?itemid=55ec2a72-a5b9-… (the government news item of 1 July 2025 (an announcement) -> the English edition of the plan in the government library, the plan's own text (rule 7c); the English edition is one of the issuer's own texts, carries the ISBN in official_identifier and is the record's english_version)
- **IS-01** secondary_url: https://www.stjornarradid.is/library/?itemid=55ec2a72-a5b9-… → https://www.stjornarradid.is/library/?itemid=6f0d36d4-72c8-… (the English edition (now official_url) -> the Icelandic edition in the government library, the original-language text that gives original_title)
- **IS-01** scope_note: National AI action plan whose main focus is benefit, busine… → Existing scope_note kept: action plan whose safety content … (pipeline run 2026-10-18-refresh-level-rule-2 (refresh), candidate IS-01)
- **UA-01** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **G20-01** date_published: 2025-11-22 → 2025-11 (2025-11-22 -> 2025-11: the declaration's own text gives only the summit's dates ('on 22 and 23 November 2025'), not the day of adoption; the day comes from the President's address at the leaders' reception, a speech (announcement), and from SAnews, so it moves to the notes with its sources (rule 7b), as for ASEAN-01's two-day meeting)
- **G20-01** notes: Adopted at the very start of the summit on 22 November 2025… → Adopted on 22 November 2025, the first day of the summit, i… (first sentence now names the sources of the adoption day (the Presidency's text of the address of 22 November 2025 and SAnews of 23 November 2025) and says the declaration itself gives only the summit's dates; the rest unchanged)
- **G20-01** scope_note: A general G20 summit declaration whose AI content is limite… → Existing scope_note kept: general summit declaration with a… (pipeline run 2026-10-18-refresh-level-rule-2 (refresh), candidate G20-01)
- **ID-02** notes: On 11 February 2026 an inter-ministerial committee of more … → Presidential Decree 38/2025 of 22 December 2025 places both… (Presidential Decree 38/2025 added (both drafts in the 2026 programme; roadmap listed for 2026-2030; the ethics regulation's subject matter); the period agreed up to 2029 at the plenary of 11 Feb 2026 added; 'enforcement relies on existing law' removed because the stored Hukumonline page does not say it)
- **US-IL-03** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **SA-04** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **SI-02** date_published: 2026-03-05 → 2026 (the strategy's own text gives no adoption date; its timeline shows the final draft in January 2026, and the day of adoption (5 March 2026) rests on the Government's news release, an announcement, so the date becomes 2026 and the day moves to the notes (rule 7b))
- **SI-02** notes: Adopted by the Government on 5 March 2026 as successor to t… → The Government's news release of 5 March 2026 says the Gove… (first sentence now names the news release as the source of the day of adoption; the nine-month deadline for the action plan is stated as the strategy states it (it rested on the English release); the planned adoption date of 22 January 2026 from the strategy's timeline added)
- **BG-01** original_title: Решение № 398 на Министерския съвет от 18 юни 2025 г. за оп… → Решение № 398 от 18 юни 2025 година за определяне на национ… (the decision's heading, now readable in the stored .doc, is longer than version 1's form: it repeats the full title of Regulation (EU) 2024/1689; original_title now gives it verbatim (sentence case for the heading's capitals))
- **BG-01** summary: Decision of the Bulgarian Council of Ministers under Articl… → Decision of the Bulgarian Council of Ministers under Articl… (rewritten from the decision's own text: the reference to the high-risk AI systems of Annex III and the Minister's notification and publication duties added; the proposer and the bodies' access to AI Act documentation, which came from the Council of Ministers' sitting page and not from the decision, left out)
- **LV-02** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **KR-04** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **KR-05** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **KR-06** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **KR-07** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **KR-08** date_published: 2026-01-22 → 2026 (2026-01-22 -> 2026: the guideline's own text gives only the year (cover '2026'); the day, 22 January 2026, rests on NIA's notice of that day, an announcement, so it moves to the notes (rule 7b))
- **KR-08** notes: Dated 2026 on its cover and published with the Act's entry … → Dated 2026 on its cover (39 pages); NIA's notice of 22 Janu… (first sentence now gives the day with its source, NIA's notice of 22 January 2026; the rest is unchanged)
- **KR-08** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **BN-01** official_url: https://www.aiti.gov.bn/news/2025/guide-on-artificial-intel… → https://www.aiti.gov.bn/guide-books/guide-on-ai-governance-… (the record pointed at AITI's press release; the guide's own text (PDF on AITI's guide-books page) becomes official_url (rule 7c))
- **BN-01** secondary_url: https://www.aiti.gov.bn/guide-books/guide-on-ai-governance-… → https://www.aiti.gov.bn/news/2025/guide-on-artificial-intel… (the press release, which gives the release date and the Malay title, replaces the guide PDF, now the official_url)
- **BN-01** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **KH-01** official_url: https://mptc.gov.kh/en/2025/04/press-release-on-the-deep-di… → https://api.oecd.ai/storage//policy-initiatives/Apr2026/117… (the record pointed at MPTC's press release on the deep-dive workshop, an announcement; the draft's own text (the English PDF dated June 2025 that the OECD.AI entry links) becomes official_url (rule 7c); the OECD.AI entry stays secondary_url because it carries the Khmer title and the current status)
- **US-HI-01** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **JM-01** notes: Written by the National Artificial Intelligence Task Force,… → Written by the National Artificial Intelligence Task Force,… ('The document is undated;' removed: the PDF's cover (page 1, an image with no text layer) reads 'Prepared by The National Artificial Intelligence Task Force September 2024' when the page is viewed, so the report is not undated; the rest of the notes is unchanged)
- **JM-01** scope_note: A report written by the National AI Task Force, an expert g… → Existing scope_note kept: expert-group report published by … (pipeline run 2026-10-18-refresh-level-rule-2 (refresh), candidate JM-01)
- **JM-01** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **CN-19** date_published: 2026-09-18 → 2026-09 (2026-09-18 -> 2026-09: the draft's own text gives only the month (cover '2026 年 09月'); the day, 18 Sept 2026, comes from the call-for-comments notice, an announcement, and stays in the notes (rule 7b))
- **CN-19** official_url: https://www.tc260.org.cn/tc260/tzgg/202609/e5b82ae7aca244d1… → https://www.tc260.org.cn/tc260/tzgg/202609/e5b82ae7aca244d1… (the record pointed at the TC260 Secretariat's call-for-comments notice, an announcement that attaches the draft; the draft PDF itself, already stored, becomes official_url (rule 7c))
- **CN-19** secondary_url: - → https://www.tc260.org.cn/tc260/tzgg/202609/e5b82ae7aca244d1… (null -> the call-for-comments notice of 18 Sept 2026, which gives the release day, the notice number and the comment deadline)
- **CN-19** notes: Released for public comment by the TC260 Secretariat with n… → The TC260 Secretariat released it for public comment with n… (first two sentences reworded: the notice is named as the source of the release day, and the draft's own date (September 2026) is added; the rest is unchanged)
- **JP-12** date_published: 2026-03-27 → 2026-03 (2026-03-27 -> 2026-03: the guidelines' own text gives only the month (cover 令和８年３月); the day, 27 March 2026, comes from MIC's press release, an announcement, and is in the notes (rule 7b))
- **JP-12** official_url: https://www.soumu.go.jp/menu_news/s-news/01cyber01_02000001… → https://www.soumu.go.jp/main_content/001064122.pdf (the record pointed at MIC's press release (報道資料), an announcement; the guidelines' own text, already stored, becomes official_url (rule 7c))
- **JP-12** secondary_url: - → https://www.soumu.go.jp/menu_news/s-news/01cyber01_02000001… (null -> MIC's press release of 27 March 2026, which gives the day of publication, the comment period and count and the AI Security Subcommittee)
- **JP-12** notes: A draft was open for public comment from 26 Dec 2025 to 29 … → MIC announced the final guidelines in a press release of 27… (first sentence added: the day of publication with its source (MIC's press release) and the guidelines' own date; the rest is unchanged)
- **US-CA-14** notes: Vetoed on 13 Oct 2025; date_published is the veto date. In … → Vetoed on 13 Oct 2025; date_published is the veto date. Con… (adds that consideration of the veto was stricken from the Assembly file on 22 Jan 2026 and the Code chapter the bill would have added, both from the Assembly's record; the rest unchanged)
- **FR-02** scope_note: Mainly a strategy for AI research, talent, data and funding… → Mainly a strategy for AI research, talent, data and funding… (the published scope_note was a reviewer's remark ('the existing scope_note is appropriate'); rewritten as a public statement of why the strategy is borderline and included)
- **FR-02** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **GB-10** scope_note: Private member's bill with little chance of passing; the ex… → A Private Members' Bill under the Ten Minute Rule, a proced… (the published scope_note was a reviewer's remark ('the existing scope_note is kept', 'rests on secondary reporting, not on a stored official file'); rewritten as a public statement of why the bill is borderline and included, from Parliament's own description of Ten Minute Rule bills)
- **GB-10** verification.level: C → A (level computed from the evidence by tools/pipeline.py)

## Re-verified without change

NL-01

## Needs a human



None.

## Merged with an open question

The run's checked corrections are merged; these points about values it left as published are open questions (GitHub issues, `pipeline.py questions --sync`).

- US-CA-02: the checker found something possibly newer: {'url': 'https://www.senate.ca.gov/media/4621', 'what': 'Senate Weekly History No. 67 of 1 Oct 2026: SB 1000 (Becker), Chapter 861, Statutes of 2026, amending the California AI Transparency Act; urgency statute, effective immediately. Affects summary, notes and possibly date_in_force; the run does n
- US-IL-02: the checker found something possibly newer: https://ilga.gov/Legislation/PublicActs/PrinterFriendly/104-0054
- KR-05: issuing_body is unsupported and the checker gave no evidence-backed fix; date_last_updated is unsupported and the checker gave no evidence-backed fix; the checker found something possibly newer: {'what': 'KOSA help desk version of Feb 2026 (최첨단 인공지능 안전성 확보 가이드라인)', 'where': 'sw.or.kr', 'note': 'not an official host, robots.txt blocks the archiver; no final notification found'}
- BN-01: checker: The guide's own PDF on aiti.gov.bn now backs the title, issuer and non-binding character (official); the date rests on the press release (alt-official), so level B. A Second Edition is listed on AITI's own site and may replace the stored edition, so the status 'current' and possibly the date and title need a person or a later run to read it.; status is unsupported and the checker gave no evidence-backed fix; the checker found something possibly newer: {'what': 'Guide on AI Governance and Ethics for Brunei Darussalam (Second Edition)', 'where': 'https://www.aiti.gov.bn/regulatory/ai-governance-and-ethics', 'note': 'listed for download, shown in a flowpaper viewer; undated'}; {'url': 'https://78460737.flowpaper.com/GuideonAIGovernanceandEthicsforBr
- FR-02: the checker found something possibly newer: {'url': 'https://www.info.gouv.fr/actualite/ia-une-nouvelle-impulsion-pour-la-strategie-nationale', 'what': 'Third stage of the national AI strategy announced after the interministerial committee of 6 Feb 2025; not stored; does not change the fields this run sets.'}; https://www.economie.gouv.fr/la-

## Not added

None.

## Repeatability

Blind second extraction of 5 candidate(s) (AGENTS.md section 7.4).

| Field | Compared | Agree |
|---|---:|---:|
| decision | 5 | 5 |
| official_identifier | 1 | 0 |

## Human sample

Check these records against their stored sources, then log the result, for example:

    python3 tools/pipeline.py log-human --run 2026-10-18-refresh-level-rule-2 --id IS-01 --result ok --note "..."

- [ ] IS-01 Iceland AI Action Plan 2025-2027
- [ ] KR-04 Korea AI transparency guideline (Art. 31)
- [ ] KR-05 Korea frontier AI safety guideline (Art. 32, draft)
- [ ] LV-02 Latvia AI Act implementation report (2025)
- [ ] NL-01 Netherlands AI Act implementation act (draft)

## Leads and open questions

- lead from LV-02: {"title": "Informatīvais ziņojums 'Par aizsardzības resora uzdevumiem saistībā ar Mākslīgā intelekta akta prasību ieviešanu' (Latvia, 2025)", "url": "https://tapportals.mk.gov.lv/attachments/legal_acts/document_versions/bd8a75c9-67a8-4150-a3e1-4296297f17cf/download", "note": "Informative report on the defence sector's tasks under the AI Act, seen in search results on the Cabinet's TAP portal; not opened; not in the register."}
- lead from SA-04: {"title": "Basic Statute of the International Centre for Artificial Intelligence Research and Ethics (Council of Ministers resolution no. 200 of 4 Aug 2026; Royal Decree M/77 of 10 Aug 2026)", "url": null, "note": "Seen in search results (digitalpolicyalert.org, aawsat.com) while checking SA-04's status; no official URL opened; not in the register."}
- BN-01: AITI's AI governance page lists a 'Second Edition' of the guide, shown only in a flipbook viewer without readable text; its date and whether it replaces the edition stored are unknown.
- BN-01: The guide stored is in English only; the Malay title appears only in AITI's bilingual press release, and no Malay text of the guide is stored. Whether 'language: English, Malay' should be 'English' is open.
- GB-10: official_identifier 'Bill 4288 (Session 2026-27)' is left as published but is not a citable number: 4288 is the bill's ID in Parliament's bills database ('billId'), the API lists no publications (no printed bill number) and gives the session only as ID 40. Should the field hold the database ID or stay empty until a printed bill number appears?
- ID-02: Presidential Decree 38/2025 lists the roadmap regulation for 2026-2030, Komdigi's items of February and May 2026 give 2026-2029, and the legal bureau's FAQ once 2025-2029. The title follows Komdigi's latest items; which period the enacted regulation will carry is open.
- ID-02: No text of either draft regulation is stored or known to be published. Whether Presidential Decree 38/2025, a formal record of the drafting programme, counts as an official register for the level is for the checker to judge.
- JM-01: The report's cover (page 1 of the PDF) is an image without a text layer; viewed, it reads 'Prepared by The National Artificial Intelligence Task Force September 2024'. textify OCRs only PDFs that are scans throughout, so the cover's date cannot be quoted. Should date_published be the report's own date (2024-09, which would be official evidence once the cover has a text layer) or the OPM's publication (2025-02, an announcement), as now?
- KH-01: The draft's own text is stored only from OECD.AI's file storage, linked from the entry Cambodia's national contact point maintains; no copy on an MPTC site is stored. Whether that copy counts as the issuer's publication (official) or as another official body's (alt-official) is for the checker to judge.
- KR-05: date_last_updated '2026-02' and the KOSA help desk named in issuing_body rest on the help desk's later version of the guideline (draft notification No. 2026-126 of February 2026, titled '최첨단 인공지능 안전성 확보 가이드라인'), which no stored file supports: sw.or.kr refuses automated downloads and is listed as not official. Either a person provides that version (archive.py --provide) or an official copy of it is found, or both values lose their support and should be reconsidered.
- KR-06: The cover and contents page of the guideline show the issuer's own English title, 'Guidelines for Determining High-Impact AI Systems', as images without a text layer, so it cannot be quoted; the record's title is a rendering of the Korean title. With an OCR text layer for pages 1 and 3 (or a maintainer's decision), the title could become the issuer's English title.
- LV-02: The report's own text is not stored: the TAP portal's robots.txt does not allow the archiver to download it. A person could provide the version the Cabinet considered on 25 February 2025 (AGENTS.md section 7.8); with it, or with the Cabinet's protocol decision for that sitting, the record could rest on the instrument's own text. Until then it rests on VARAM's release and is level B.
- NL-01: original_title ('Wetsvoorstel tot uitvoering van de verordening artificiële intelligentie (Uitvoeringswet AI-verordening)') is left as published but no stored file supports it: the draft bill on internetconsultatie.nl cannot be stored because the site's robots.txt disallows automated downloads. A person could provide the consultation version of the draft bill with the 'Provide a document' form; it would also bring the record to level A.
- SA-04: The draft's own text (Istitlaa, 'Global AI Hub Law EN-AR - Final Draft for PC') is not stored: the platform times out for the archiver. Until it is, the record rests on CST's releases and is level B; a person could provide the PDF (AGENTS.md section 7.8).
- UA-01: The roadmap's own text (PDF on cms.thedigital.gov.ua) could not be stored (timeouts on 17 and 18 Oct 2026), so the record rests on announcements and is level B. A person could provide the PDF (AGENTS.md section 7.8); once stored, it should become official_url.
- US-CA-01: The statute's own text (Civil Code sections 3110 and 3111 as added by Chapter 817, Statutes of 2024) is still not stored: leginfo.legislature.ca.gov refuses the archiver. A person could provide it with the 'Provide a document' form; official_url would then point at the statute instead of the Governor's release.
- US-CA-02: SB 1000 (Becker), approved by the Governor and chaptered on 30 Sep 2026 as Chapter 861, Statutes of 2026, amends Sections 22757.1, 22757.2, 22757.3, 22757.4 and 22757.5 of the Business and Professions Code (the Act's definitions, detection-tool, disclosure, penalty and related sections) and adds and repeals Section 22757.4.1, as an urgency statute that takes effect immediately. This is in the Senate Weekly History of 1 Oct 2026 (https://www.senate.ca.gov/media/4621, stored in this run under US-CA-06), not in a stored source of this record. Its text is not stored, so whether it changes the covered-provider duties, their operative date of 2 Aug 2026, the penalty or the summary is open. A refresh of this record should store the Senate history (and, if a person can provide it, the chaptered text) and add Chapter 861 to official_identifier and the notes.
- US-CA-02: The text of AB 2713 as enacted (Chapter 856, Statutes of 2026; amended in the Senate on 21 Aug 2026) is not stored, so how it changed Section 22757.3.1 is described only from the committee analysis of April 2026.
- US-CA-02: The statute's own text is still not stored: leginfo.legislature.ca.gov refuses the archiver. official_url stays the Governor's release of 29 Sep 2024.
- US-CA-06: The texts of SB 867 (Chapter 189) and SB 1119 (Chapter 190), Statutes of 2026, are not stored, so what they change in Sections 22601 and 22602 and when the changes take effect is open; the summary describes SB 243 as enacted in 2025.
- US-CA-06: The statute's own text is still not stored: leginfo.legislature.ca.gov refuses the archiver. official_url stays the Governor's release of 13 Oct 2025.
- US-CA-07: date_in_force stays null: no stored file gives the effective date of Chapters 178 and 179, Statutes of 2026 (the statutes' text on leginfo.legislature.ca.gov refuses the archiver). A person could provide the chaptered texts with the 'Provide a document' form; official_url would then point at them instead of the Governor's release.
- US-CA-08: date_in_force stays null: no stored file gives the effective date of Chapter 190, Statutes of 2026 (the bill's text on leginfo.legislature.ca.gov refuses the archiver). A person could provide the chaptered text with the 'Provide a document' form; official_url would then point at it instead of the Governor's release.
- US-CA-14: The enrolled text of AB 1064 is not stored (leginfo.legislature.ca.gov refuses the archiver), so the definitions of the bill as passed rest on the veto message; official_url (the bill's leginfo page) has never been stored.
- US-HI-01: date_in_force (2026-07-14) rests only on a secondary tracker, and the Act's text has not been read; data.capitol.hawaii.gov refuses automated downloads. This is the question already open in issue #147; a person could provide the Act (Governor's Message No. 1350 or SB 3001 CD1) with the 'Provide a document' form.
- US-IL-02: The Act's text and the General Assembly's record of HB 1806 are not stored: ilga.gov is unreachable from the archiver's network. The Public Act number (104-0054, from a web search) and the '104th General Assembly' in official_identifier rest on no stored source. A person could provide the Public Act with the 'Provide a document' form; official_url would then point at it and the record could reach level A.
- US-IL-03: official_identifier 'SB 315 (104th General Assembly)': the stored release shows SB 315 but not the General Assembly, and gives no Public Act number. Both need the Act's text or the bill-status page on ilga.gov, which refuses the archiver. A person could provide the enrolled Act with the 'Provide a document' form.
- US-IL-03: Secondary summaries found today say that some obligations (the frontier AI framework and the independent audits) apply only from 1 Jan 2028, while the release gives 1 Jan 2027 for the law as a whole. The Act's text is needed to confirm whether its duties are phased; until then date_in_force follows the release.
