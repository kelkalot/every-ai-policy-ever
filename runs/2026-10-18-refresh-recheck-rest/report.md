# Run 2026-10-18-refresh-recheck-rest

<!-- coordinator: one paragraph here on what a human should look at first -->
The last two records of the first monthly recheck, both held back by earlier parts. PH-01 rests for the first time on a stored copy: privacy.gov.ph refuses the archiver, so the maintainer stored the signed NPC Advisory No. 2024-04 with archive.py --provide (#155). The title is now the advisory's full subject, and the summary and notes keep only what the advisory says. EC-01 follows the maintainer's decision on #150, which makes it the unified bill text the Plenary archived. The committee's first-debate report of 31 Aug 2026 (now official_url) and the Plenary minutes, Acta 123 of 15 Sep 2026, replace the press releases as its evidence. The notes now name the two initiatives the report says were unified (Núñez 450889 and Subía), not three; Correa's bill appears only as the report describes it. Both records stay at A, now on the instrument's own records. Look first at the summary of EC-01, which rests on the report's description of the unified text because the text itself is not stored. The blind extraction chose the Plenary minutes rather than the report as official_url; the checker found either defensible.

Type: refresh. Scope: ids:EC-01,PH-01. Started 2026-10-18; report written 2026-10-18.

| Stage | Tool | Model | Date |
|---|---|---|---|
| collect | - | - | - |
| extract | Claude Code | claude-opus-5-5 | 2026-10-18 |
| blind | Claude Code | claude-sonnet-5-5 | 2026-10-18 |
| check | Claude Code | claude-sonnet-5-5 | 2026-10-18 |

## Summary

- Candidates: 2 (active 2)
- Added: 0; fields changed: 9 in 2 record(s); re-verified without change: 0
- Not added: 0; need a human: 0; not ready: 0
- Repeatability: 0% field agreement between blind double extractions (2 pair(s)); 96% agreement on the resulting records (23 field values; in a refresh run the first figure counts only fields that an extraction changed)

## Added

None.

## Changed

- **EC-01** official_url: https://www.asambleanacional.gob.ec/es/noticia/119354-pleno… → https://repositorioctic.asambleanacional.gob.ec/share/proxy… (the Assembly's news release of 15 Sep 2026 (an announcement) -> the committee's first-debate report of 31 Aug 2026, the Assembly's official record of the unified bill, stored in this run (rule 7c; the unified text itself is not published among the stored sources))
- **EC-01** secondary_url: https://www.asambleanacional.gob.ec/es/node/118898 → https://www.asambleanacional.gob.ec/es/noticia/119354-pleno… (the news release of 31 Aug 2026 -> the news release of 15 Sep 2026 on the archiving, which the official URL no longer covers)
- **EC-01** summary: Ecuador's first general AI bill, consolidating initiatives … → Unified bill for an organic law regulating and promoting AI… (rewritten from the committee report's description of the unified text (section 5.1, 5.2), as the maintainer decided in issue #150: drops 'first general AI bill' and 'regulate algorithms', adds its EU AI Act model, contents and governance bodies)
- **EC-01** safety_topics: + prohibited practices, + general-purpose / frontier AI (adds 'prohibited practices' and 'general-purpose / frontier AI', both in the report's list of the text's contents (prácticas prohibidas; reglas para IA generativa/modelos de propósito general))
- **EC-01** notes: The committee said the archiving does not abandon AI regula… → The committee unified two initiatives: the bill of the same… (rewritten from the report and the minutes: the two initiatives unified (Núñez, Subía) with their dates, the Correa bill only as the report describes it, the committee's findings and vote, the discrepancy inside the report, and the Plenary vote; the process remark moved to verification.note)
- **EC-01** english_version: - → {"kind": "none found"} (added: none found)
- **PH-01** title: NPC Advisory No. 2024-04: Guidelines on the Application of … → NPC Advisory No. 2024-04: Guidelines on the Application of … (the shortened title -> the full official subject of the advisory, as the WHEREFORE clause and the heading give it (adds 'Republic Act No. 10173 or the' and '(DPA)'))
- **PH-01** summary: Guidance from the Philippine data protection regulator on h… → Advisory of the Philippine National Privacy Commission on h… (rewritten from the stored text: drops 'profiling' and 'security measures proportionate to AI risks', which the advisory does not say, and adds its accountability, governance (PIA, monitoring, AI ethics board), human intervention and contestation of automated decisions, bias and AI-washing provisions)
- **PH-01** notes: Signed by Privacy Commissioner John Henry D. Naga and Deput… → Signed by Privacy Commissioner John Henry D. Naga and Deput… (kept the signatories; added the legal basis and the sources of the AI definition from the advisory; dropped the claims that NPC advisories are not regulations, that it was issued alongside Advisory 2024-03 and that AI bills are pending, which no stored source supports)

## Re-verified without change

None.

## Needs a human



None.

## Merged with an open question



None.

## Not added

None.

## Repeatability

Blind second extraction of 2 candidate(s) (AGENTS.md section 7.4).

| Field | Compared | Agree |
|---|---:|---:|
| decision | 2 | 2 |
| title | 1 | 0 |
| safety_topics | 1 | 0 |

## Human sample

Check these records against their stored sources, then log the result, for example:

    python3 tools/pipeline.py log-human --run 2026-10-18-refresh-recheck-rest --id EC-01 --result ok --note "..."

- [ ] EC-01 Ecuador AI bill (archived 2026)
- [ ] PH-01 Philippines NPC AI advisory (2024-04)

## Leads and open questions

- EC-01: The unified text itself was not stored; the summary rests on the committee report's description of it. If the Assembly publishes the unified text (or the committee's working text of 2024-2025), a later run could store it and check the summary and topics against it.
