# Run 2026-10-18-recheck-east-asia-1

<!-- coordinator: one paragraph here on what a human should look at first -->
The first monthly recheck, part 9: 31 records of China, Hong Kong, Japan and Taiwan. Look first at a rule effect: seven TC260 standards and guides (CN-20 to CN-23, CN-25 to CN-27) fell from A to B. Their covers give only the month, and the day comes from TC260's own release notice, which each record keeps as its secondary source; section 7.6 caps a file stored in that role at alt-official. Version 1 was A only because an earlier run had stored the same notice under another role. Storing the identical file again to restore A was not done; whether the issuer's own release notice should count as official evidence is a rule decision. Other changes: CN-05 and CN-18 now rest on stored official pages; TW-02 takes MODA's English title and rose to A on the English version; HK-01 and HK-02 now have dates (2021 and 15 April 2025); JP-13's official URL now points to version 2.0 of the Digital Agency guideline (in effect from 1 September 2026); JP-11's issuing body is the Japan AI Safety Institute, with the sub-working group that wrote it named in a scope note. Not in this run: the stored version 2.0 of DS-920 dates Japan's AI Basic Plan to 23 December 2025, while JP-06 gives 14 July 2026; JP-06 should be refreshed.

Type: recheck. Scope: ids:CN-01,CN-03,CN-04,CN-05,CN-14,TW-01,TW-02,HK-01,HK-02,CN-18,CN-19,CN-20,CN-21,CN-22,CN-23,CN-24,CN-25,CN-26,CN-27,JP-07,JP-08,JP-09,JP-10,JP-11,JP-12,JP-13,JP-14,JP-15,JP-16,JP-17,CN-28. Started 2026-10-18; report written 2026-10-18.

| Stage | Tool | Model | Date |
|---|---|---|---|
| collect | - | - | - |
| extract | Claude Code | claude-opus-5-5 | 2026-10-18 |
| blind | Claude Code | claude-sonnet-5-5 | 2026-10-18 |
| check | Claude Code | claude-sonnet-5-5 | 2026-10-18 |

## Summary

- Candidates: 31 (active 31)
- Added: 0; fields changed: 63 in 27 record(s); re-verified without change: 4
- Not added: 0; need a human: 0; not ready: 0
- Repeatability: 0% field agreement between blind double extractions (5 pair(s)); 97% agreement on the resulting records (58 field values; in a refresh run the first figure counts only fields that an extraction changed)

## Added

None.

## Changed

- **CN-01** summary: China's first binding AI-specific rule (35 articles). It co… → Binding rules (35 articles) for providers using algorithmic… (rewritten from the text: version 1's opening claim that this is China's first binding AI-specific rule rests on no stored file; Art. 8 (regular review of algorithms, models, data and outcomes), Art. 16 and Art. 27 (security assessment) made explicit)
- **CN-01** safety_topics: + risk-based classification (added risk-based classification: Art. 23 sets up classified and graded security management of algorithmic recommendation services)
- **CN-01** notes: Adopted at the CAC office meeting of 16 Nov 2021, signed 31… → Adopted at the Cyberspace Administration of China's 20th of… (version 1's reference to State Council Gazette 2022 No. 9 and its remark that the filing system serves other rules rest on no stored file and were removed; Arts. 23, 24, 26 and 31 added)
- **CN-01** english_version: - → {"kind": "third-party translation", "url": "https://www.chi… (required and missing; China Law Translate's English translation, stored in this run, is a third-party translation (chinalawtranslate.com is listed as not official))
- **CN-03** notes: Adopted at the CAC office meeting of 23 May 2023, signed 10… → Adopted at the Cyberspace Administration of China's 12th of… (version 1's remarks on implementation through the CAC filing and on TC260-003 and GB/T 45654-2025 rest on no stored file and were removed, and the remark on the secondary URL is about the sources (now in verification.note); Arts. 12, 16, 17 and 20 added)
- **CN-04** summary: Cross-sector ethics review regime for science and technolog… → Trial measures that set up ethics review of science and tec… (rewritten from the text: Art. 2 scope, Art. 4 (AI units set up ethics committees), Art. 15(5) as a review criterion of the committees rather than a general requirement, and the annex's three AI-related items)
- **CN-04** safety_topics: + risk-based classification (added risk-based classification: listed higher-risk activities need expert re-review (Art. 25) and minimal-risk activities can use a simplified procedure (Art. 22))
- **CN-04** notes: Signed 7 Sept 2023, published 8–10 Oct 2023, effective 1 De… → Issued by the Ministry of Science and Technology and nine o… (publication date narrowed to 8 Oct 2023 (MOST page); version 1's 10 Oct rests on no stored file; Arts. 22, 25-34, 36 and 43-45 added)
- **CN-04** scope_note: Not AI-specific; included for its AI-related review list an… → Not AI-specific; the existing scope_note stays (AI-related … (pipeline run 2026-10-18-recheck-east-asia-1 (recheck), candidate CN-04)
- **CN-04** english_version: - → {"kind": "third-party translation", "url": "https://cset.ge… (required and missing; CSET's English translation, stored in this run, is a third-party translation (translator Etcetera Language Group, edited by CSET))
- **CN-05** secondary_url: https://www.gov.cn/lianbo/fabu/202310/content_6910006.htm → https://www.mfa.gov.cn/web/fyrbt_673021/dhdw_673027/202310/… (the gov.cn page of version 1 cannot be stored (robots.txt unreachable, then DNS failure); the MFA spokesperson's remarks of 18 Oct 2023 on mfa.gov.cn, stored in this run, give the same facts (announcement by President Xi at the Third Belt and Road Forum))
- **CN-05** notes: Announced 18 Oct 2023 by President Xi Jinping in his keynot… → Announced on 18 Oct 2023 by President Xi Jinping in his key… (version 1's claims that the Initiative is the conceptual basis of the AI Safety Governance Framework and the 2025 Action Plan, and that the MFA page was re-posted in May 2024, rest on no stored file and were removed (CN-07 and CN-11 stay linked); the CAC publication of the Chinese text on 18 Oct 2023 added)
- **CN-14** summary: Amends the Cybersecurity Law and adds a new Article 20 on A… → Decision of the NPC Standing Committee making 14 changes to… (rewritten closer to the text of the new Art. 20 (both paragraphs) and the Decision's other changes; version 1's closing sentence ('This places AI governance in national statute law') was an evaluation)
- **CN-14** notes: Adopted 28 Oct 2025 at the 18th session of the 14th NPC Sta… → Adopted on 28 Oct 2025 at the 18th session of the 14th NPC … (version 1's statement that China has not adopted a comprehensive AI law rests on no stored file, and its sentence on what the summary covers was about the record; both removed; the Decision's other changes (items 1, 4, 5, 7 and 13) added)
- **CN-14** scope_note: - → Not AI-specific: an amendment to the Cybersecurity Law, inc… (added: the Decision amends a general cybersecurity law and is in for its AI article, the case AGENTS.md section 10 gives a scope_note (a law that is not AI-specific but is the operative instrument for an AI-safety question))
- **CN-14** english_version: - → {"kind": "third-party translation", "url": "https://cset.ge… (required and missing; CSET's English translation of the Cybersecurity Law as amended by this Decision, stored in this run, is the closest English text found; a third-party translation)
- **TW-01** language: Chinese (Traditional), English → Chinese (Traditional) (the official text is Chinese only; the English text is the NSTC's translation (listed under 英譯法規清單 and stored as EngLawContent), so English moves to english_version)
- **TW-01** summary: Framework law (20 articles) setting seven principles for go… → Framework law setting seven principles for government AI po… (rewritten from the stored Chinese text, using the NSTC translation's terms: Article 5(1) protects life, body (身體), liberty or property, not 'safety'; Article 4's fourth principle is cybersecurity and safety (資安與安全); Article 16's framework is an 'AI risk taxonomy and assessment framework'; the duty to restrict or prohibit such uses comes from Article 16(2))
- **TW-01** notes: Promulgated 14 Jan 2026 and in force on promulgation (Art. … → Enacted in full (20 articles) by presidential order promulg… (the sentence on the Legislative Yuan's passage in late December 2025 rests on no stored file and was removed; enactment in full by presidential order (history page), Article 6 (National AI Strategic Committee, as the translation names it) and Article 5(2) added; Article 18 restated more exactly)
- **TW-01** english_version: - → {"kind": "government translation", "url": "https://law.nstc… (the record had none; the NSTC's English translation of the Act is now stored at the recorded URL)
- **TW-02** title: Artificial Intelligence Risk Classification Framework (v1.0) → Artificial Intelligence Risk Taxonomy and Assessment Framew… (MODA's English version of the framework is titled 'Artificial Intelligence Risk Taxonomy and Assessment Framework' (its English page: 'AI Risk Taxonomy and Assessment Framework'); the previous title was a rendering of 人工智慧風險分類框架. The version label moved to notes)
- **TW-02** short_title: Taiwan AI Risk Classification Framework → Taiwan AI Risk Taxonomy and Assessment Framework (follows the new English title)
- **TW-02** summary: Framework issued under Article 16 of the AI Basic Act to gu… → Framework made by MODA under Article 16 of the AI Basic Act… (rewritten from the Chinese text with the terms of MODA's English version (risk subtypes, the three risk-type names, the four steps); it now states that regulators must follow the workflow (2.1))
- **TW-02** notes: Version 1.0 is dated 7 Jul 2026 (ROC 115-07-07). The MODA p… → Version 1.0 is dated 7 Jul 2026 (ROC 115-07-07); MODA's Eng… (the reference to MODA's AI Evaluation Center (AIEC) rests on no stored file and was removed; the hedge about an earlier draft was removed (page dates are in verification.note); the civilian scope and military exclusion (2.2), the measures for high-risk and unmanageable use cases (3.4.1(b) iii and iv), the periodic review (3.2.3) and the English version added)
- **TW-02** english_version: - → {"kind": "government translation", "url": "https://www-api.… (the record had none; MODA publishes an English version of version 1.0, now stored)
- **HK-01** date_published: - → 2021 (was null; the Secretary for Innovation, Technology and Industry's speech of 30 Oct 2025 says the framework was 'first introduced in 2021', so the year is recorded at that precision)
- **HK-01** notes: Current text is version 2.0 (December 2025). Earlier versio… → First introduced in 2021 and updated in 2023, according to … (the year of first introduction and the 2023 update added from the speech; the remark that the release date of version 1.0 is left null concerns the record and was removed; version 2.0's changes, the adaptation for general use and the English-prevails clause added from the PDF)
- **HK-02** date_published: - → 2025-04-15 (was null; the HKSAR Government press release of 15 Apr 2025 says the DPO released the guideline that day)
- **HK-02** notes: Current text is version 1.1 (December 2025). The document d… → Released by the Digital Policy Office on 15 Apr 2025; the c… (release date and HKGAI's founding and AIR@InnoHK funding added from the press release; the remarks on why date_published was empty and that the guideline was 'reportedly first issued in April 2025 (not verified)' concern the research and were removed; the English-prevails clause added from the PDF)
- **CN-18** summary: Draft recommended national standard, proposed by TC260, tha… → Draft recommended national standard, proposed by TC260, tha… (corrected: the draft does not rate every process area on all ten capabilities; each selects the relevant ones (5.2.1 note); PA37 given its full name, 'security operations and emergency intervention')
- **CN-18** safety_topics: + catastrophic risk (added catastrophic risk: the top levels require that safeguards against biological-weapon and cyberattack knowledge survive agent use, and human uplift trials on attack code and biological harm (PA15 and PA17, level 5))
- **CN-18** related: + CN-24, + CN-20 (added CN-24 (GB/T 45674-2025, a normative reference) and CN-20 (TC260's AI application security guide, which refers to the national standard on AI security capability maturity assessment for maturity levels))
- **CN-18** notes: TC260 opened the draft for comment on 26 Aug 2026, with com… → TC260 opened the draft for comment on 26 Aug 2026, with com… (the organisation-level rule completed with clause 9.6.2 c); the human uplift trials at the top level of PA17 added; GB/T 45674-2025 linked as CN-24)
- **CN-19** related: + CN-26 (added CN-26: the draft's bibliography lists TC260's practice guide on the security of deploying and using agents, which is CN-26)
- **CN-19** notes: Released for public comment by the TC260 Secretariat with n… → Released for public comment by the TC260 Secretariat with n… (the bibliography item linked as CN-26)
- **CN-20** related: + CN-24, + CN-18 (added CN-24 (GB/T 45674-2025, a normative reference, clause 2) and CN-18 (the draft national standard on AI security capability maturity assessment, the kind of standard clause 7.1 d) refers to for maturity levels))
- **CN-20** notes: Version v1.0-202609, released on 15 Sept 2026 with notice 网… → Version v1.0-202609, released on 15 Sept 2026 with notice 网… (GB/T 45674-2025 linked as CN-24)
- **CN-20** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **CN-21** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **CN-22** related: + CN-24 (added CN-24 (GB/T 45674), a normative reference of the guide)
- **CN-22** notes: Version v1.0-202609, released on 15 Sept 2026 with notice 网… → Version v1.0-202609, released on 15 Sept 2026 with notice 网… (added the normative references, among them GB/T 45674 (CN-24), with record IDs; the rule on subgroups now gives both options of clause 7.2 b) (restricted use or a clear warning of lower confidence) instead of restricted use alone)
- **CN-22** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **CN-23** related: + CN-24 (added CN-24 (GB/T 45674), which clause 7 f) requires training-data work to meet)
- **CN-23** notes: Version v1.0-202609, released on 15 Sept 2026 with notice 网… → Version v1.0-202609, released on 15 Sept 2026 with notice 网… (GB/T 45674 now carries its record ID (CN-24), and the training-data clause names collection, annotation and management as clause 7 f) does)
- **CN-23** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **CN-24** notes: Published 25 Apr 2025 and effective 1 Nov 2025. It is a rec… → Published 25 Apr 2025 and effective 1 Nov 2025. It is a rec… (removed the remark that GB/T 45654-2025 names this standard as a companion standard: that is a statement about CN-10's text (it stays in CN-10's notes) and no file stored for this record shows it)
- **CN-25** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **CN-26** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **CN-27** verification.level: A → B (level computed from the evidence by tools/pipeline.py)
- **JP-09** scope_note: Mainly a data management guidebook; included because the Ja… → Existing scope_note kept. (pipeline run 2026-10-18-recheck-east-asia-1 (recheck), candidate JP-09)
- **JP-10** scope_note: A discussion paper rather than guidance, which says it does… → Existing scope_note kept. (pipeline run 2026-10-18-recheck-east-asia-1 (recheck), candidate JP-10)
- **JP-11** original_title: ヘルスケア領域におけるAIセーフティ評価観点ガイド → ヘルスケア領域におけるAIセーフティ評価観点ガイド ～Trustworthy AI（信頼できるAI）の実現を目指して～ (the Japanese cover carries the subtitle ～Trustworthy AI（信頼できる AI）の実現を目指して～, which the English title already renders ('Toward the Realization of Trustworthy AI'); added so that the two titles correspond)
- **JP-11** issuing_body: Japan AI Safety Institute (J-AISI), Healthcare Sub-Working … → Japan AI Safety Institute (J-AISI) (the guide is a J-AISI output written by a sub-working group of companies that J-AISI set up (7.1, page 117 of the Japanese text); under the rule for reports an authority publishes that a group it convened wrote, the issuing body is the authority and the notes name the authors)
- **JP-11** notes: J-AISI's list of outputs dates the release 2 April 2026; th… → Written by the Healthcare Sub-Working Group of the Business… (authorship added from chapter 7 (SWG led by Ubie with company members, secretariat Mitsubishi Research Institute, with JaDHA's SubWG-B); the release page lists the Markdown files of chapters 3 and 4 only in Japanese, so that sentence was corrected)
- **JP-11** scope_note: - → Written by the Healthcare Sub-Working Group, a group of com… (added under the same rule, naming the sub-working group and the Japan Digital Health Alliance's working group)
- **JP-13** official_url: https://www.digital.go.jp/news/3579c42d-b11c-4756-b66e-3d3e… → https://www.digital.go.jp/news/decb64eb-f26e-41cb-8d37-f3dd… (the first decision's news page (the old official_url) says it does not show the latest version; the news page on version 2.0 is the Digital Agency's page for the current text and links the Japanese text and the English translation)
- **JP-13** notes: A normative document of the Digital Society Promotion Stand… → A normative document of the Digital Society Promotion Stand… (the supplementary provisions of version 2.0 (CAIO measures by 30 June 2026, governance-framework scope from 1 July 2026) added; the reference to 'the guideline under Article 13 of the AI Act' replaced by the instruments version 2.0 itself names (section 1.1), since the stored text does not cite Article 13)
- **JP-14** summary: Alert of the Personal Information Protection Commission on … → Alert of the Personal Information Protection Commission on … (Annex 1 (1)② makes input of personal data 'without the person's prior consent' a possible breach for businesses, while (2)② for administrative bodies has no consent condition; version 1 applied 'without consent' to both. The sentence now follows the text, and the advice to check that the provider does not use the data for machine learning, which both items give, is added)
- **JP-14** scope_note: An alert (注意喚起) by Japan's data protection authority to bus… → Existing scope_note kept. (pipeline run 2026-10-18-recheck-east-asia-1 (recheck), candidate JP-14)
- **JP-16** notes: Version 2.0 of 26 Dec 2024 revised the provisional guidelin… → Version 2.0 of 26 Dec 2024 revised the provisional guidelin… (the two English renderings MEXT uses for the title (its pages and the cover of its provisional translation) are now noted)
- **JP-16** scope_note: Mainly guidance on using generative AI in teaching and scho… → Existing scope_note kept. (pipeline run 2026-10-18-recheck-east-asia-1 (recheck), candidate JP-16)
- **JP-17** notes: The AI Institutional Study Group was set up in July 2024 un… → The AI Institutional Study Group was set up in July 2024 un… (the Act's title now follows record JP-04 ('Artificial Intelligence-related Technology' for 'AI-related Technology'); the rest is confirmed against the Japanese text)
- **CN-28** scope_note: Mainly a national plan for AI research, industry and adopti… → Mainly a development plan; existing scope_note stays. (pipeline run 2026-10-18-recheck-east-asia-1 (recheck), candidate CN-28)

## Re-verified without change

JP-07, JP-08, JP-12, JP-15

## Needs a human



None.

## Merged with an open question



None.

## Not added

None.

## Repeatability

Blind second extraction of 5 candidate(s) (AGENTS.md section 7.4).

| Field | Compared | Agree |
|---|---:|---:|
| decision | 5 | 5 |
| original_title | 1 | 0 |
| issuing_body | 1 | 0 |
| safety_topics | 1 | 0 |

## Human sample

Check these records against their stored sources, then log the result, for example:

    python3 tools/pipeline.py log-human --run 2026-10-18-recheck-east-asia-1 --id CN-18 --result ok --note "..."

- [ ] CN-18 Draft national standard on AI security capability maturity assessment
- [ ] CN-22 TC260-PG-202610A (AI application security, health)
- [ ] CN-25 TC260-PG-202515A (generative AI security emergency response)
- [ ] HK-01 Hong Kong Ethical AI Framework
- [ ] JP-08 J-AISI Chief AI Officer (CAIO) Guides

## Leads and open questions

- lead from CN-22: {"title": "TC260-005 人工智能应用伦理安全指引 1.0 (AI Application Ethics Security Guidelines 1.0), TC260, May 2026", "url": null, "seen_in": "archive/_runs/2026-10-14-discover-leads-2026-10-14/C005/2026-10-14/official.pdf, page 6 (normative references) and page 25 (references: '人工智能应用伦理安全指引 1.0 2026 年 5 月')", "why": "A TC260 document on the ethics and safety of AI applications that the health guide (and TC260-PG-20267A, CN-27) cite; not in the register."}
- lead from CN-24: {"title": "20264769-T-469 网络安全技术 人工智能深度合成安全规范 (Cybersecurity technology: security specification for AI deep synthesis), national standard plan", "url": null, "seen_in": "archive/CN-24/2026-10-18/secondary.html (std.samr.gov.cn, list 相近标准(计划))", "why": "A planned recommended national standard on AI deep-synthesis security under TC260; a draft for comment may exist."}
- lead from CN-24: {"title": "20264764-T-469 网络安全技术 人工智能模型开发安全指南 (Cybersecurity technology: security guide for AI model development), national standard plan", "url": null, "seen_in": "archive/CN-24/2026-10-18/secondary.html (std.samr.gov.cn, list 相近标准(计划))", "why": "A planned national standard on the security of AI model development; a draft for comment may exist."}
- lead from CN-24: {"title": "20263724-Z-469, 20263726-Z-469 and 20263725-Z-469 网络安全技术 人工智能应用安全 教育 / 金融 / 应急管理 (AI application security for education, finance and emergency management), guiding technical document plans", "url": null, "seen_in": "archive/CN-24/2026-10-18/secondary.html (std.samr.gov.cn, list 相近标准(计划))", "why": "Planned national guiding technical documents on AI application security by sector; the education one may become the national-standard version of TC260-PG-20269A (CN-21), and finance and emergency management have no record yet."}
- lead from CN-24: {"title": "20264763-T-469 网络安全技术 生成式人工智能系统互操作安全规范 (security specification for interoperability of generative AI systems), national standard plan", "url": null, "seen_in": "archive/CN-24/2026-10-18/secondary.html (std.samr.gov.cn, list 相近标准(计划))", "why": "A planned national standard on generative AI system interoperability security."}
- lead from CN-24: {"title": "YD/T 6931-2026 人工智能 安全治理 生成式人工智能图像检测服务系统能力要求 (AI safety governance: capability requirements for generative AI image detection service systems), telecommunications industry standard", "url": null, "seen_in": "archive/CN-24/2026-10-18/secondary.html (std.samr.gov.cn, list 相近标准(计划))", "why": "A published industry standard on detecting AI-generated images, under 'AI safety governance'; not in the register."}
- lead from CN-24: {"title": "DB43/T 3538-2026 人工智能行业数据标注服务安全规范 (security specification for data annotation services in the AI industry), Hunan provincial local standard", "url": null, "seen_in": "archive/CN-24/2026-10-18/secondary.html (std.samr.gov.cn, list 相近标准(计划))", "why": "A sub-national standard on AI data-annotation security, the local counterpart of GB/T 45674; not in the register."}
- lead from CN-27: {"title": "TC260-005 人工智能应用伦理安全指引 1.0 (AI Application Ethics Security Guidelines 1.0), TC260", "url": null, "seen_in": "archive/_runs/2026-10-14-discover-leads-2026-10-14/C011/2026-10-14/official.pdf, page 6 (note to 5 d)) and page 10 (references)", "why": "TC260 document on the ethical safety impact of AI applications, cited here and in the health guide (CN-22); not in the register."}
- lead from JP-08: {"title": "AIロボティクスに関するセーフティ評価観点ガイド (J-AISI guide to AI safety evaluation perspectives for AI robotics)", "url": "https://aisi.go.jp/output/output_information/260723/", "seen_in": "archive/_runs/2026-10-18-recheck-east-asia-1/JP-08/extra-cce5ea29b8/2026-10-18/official.html (J-AISI list of Information outputs, entry of 2026年7月23日)", "why": "J-AISI AI safety evaluation guide for robotics released 23 Jul 2026; no record in the register."}
- lead from JP-08: {"title": "AIセーフティ年次レポート2025 / National Status Report on AI Safety in Japan 2025", "url": "https://aisi.go.jp/output/output_information/260428/", "seen_in": "archive/_runs/2026-10-18-recheck-east-asia-1/JP-08/extra-cce5ea29b8/2026-10-18/official.html (J-AISI list of Information outputs, entry of 2026年4月28日)", "why": "J-AISI's annual national status report on AI safety, released 28 Apr 2026; no record in the register."}
- lead from JP-08: {"title": "AIセーフティ・アプローチブック（AIセーフティの普及に向けた文書）", "url": "https://aisi.go.jp/output/output_information/250326/", "seen_in": "archive/_runs/2026-10-18-recheck-east-asia-1/JP-08/extra-cce5ea29b8/2026-10-18/official.html (J-AISI list of Information outputs, entry of 2025年3月26日)", "why": "J-AISI document on promoting AI safety, released 26 Mar 2025; no record in the register."}
- CN-14: The number of the presidential order that promulgated the Decision (official_identifier) is in no stored file.
- CN-20: The full date of release (2026-09-15) rests on the issuer's own release notice (网安秘字〔2026〕118号), which is stored as the record's secondary source and so counts as alt-official; the guide's PDF gives only September 2026, so the record stays at level B.
- TW-01: date_in_force is the promulgation date (14 Jan 2026), following Article 20 ('本法自公布之日起施行'). Taiwan's Central Regulation Standard Act (中央法規標準法), Article 13, is generally read as making a law that takes effect from promulgation effective on the third day counted from the promulgation day, which would give 16 Jan 2026. No stored file holds that Act, so the record keeps 14 Jan 2026; a maintainer may settle whether Article 13 applies and, if so, set date_in_force to 2026-01-16 with the Act as source.
- TW-01: issuing_body names the Legislative Yuan as the body that adopted the Act, but no stored page names it or the date of its third reading (the NSTC history page records only the presidential promulgation). The value is kept as published; a maintainer may confirm it from a Legislative Yuan source.
