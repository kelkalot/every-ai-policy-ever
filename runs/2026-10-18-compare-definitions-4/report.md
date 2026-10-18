# Definitions 2026-10-18-compare-definitions-4

Defined terms quoted verbatim from the stored sources of 3 records (issue #70). Every quote was checked against its stored file and SHA-256 by `tools/definitions.py check`. Similar definitions are not legally equivalent; nothing here is legal advice.

**Repeatability:** 3 of 4 pairs from two independent extractions quote the same definition, 3 the same locator.

**Checker:** accepted 3 of 3 definitions both extractions agree on. Term-group assignments for a human: 0.

- EU-03: the checker found a definition both extractions missed: general-purpose AI model (Article 3(65) defines 'systemic risk' and Article 3(66) 'general-purpose AI system' (related terms, outside the plan's groups); high-risk AI systems are classified in Article 6, not defined in Article 3.)
- TW-01: the checker found a definition both extractions missed: artificial intelligence (Article 3 defines 人工智慧 (the AI definition, line 89 of the official text layer) and the first extraction quoted it correctly with a faithful English rendering, but the blind extraction did not find it, so it is not in agreement and cannot be merged this run. I would accept it if both agree next time.)

**Effort:** about 80,329 tokens per record for extraction, blind extraction and check together (extract 106,404, blind 71,969, check 62,614).

**Earlier definitions not quoted again in this run** (they stay as they are; the app marks one whose source changed): D0009 (TW-01, artificial intelligence).

## AI system

| Record | Term | Definition | Where |
|---|---|---|---|
| EU-03 EU AI Act | AI system | ‘AI system’ means a machine-based system that is designed to operate with varying levels of autonomy and that may exhibit adaptiveness after deployment, and that, for explicit or implicit objectives, infers, from the input it receives, how to generate outputs such as predictions, content, recommendations, or decisions that can influence physical or virtual environments | Article 3, point (1) |
| OECD-01 OECD AI Principles | AI system | An AI system is a machine-based system that, for explicit or implicit objectives, infers, from the input it receives, how to generate outputs such as predictions, content, recommendations, or decisions that can influence physical or virtual environments. Different AI systems vary in their levels of autonomy and adaptiveness after deployment. | Paragraph I, 'AI system', page 2 |

## general-purpose AI model

| Record | Term | Definition | Where |
|---|---|---|---|
| EU-03 EU AI Act | general-purpose AI model | ‘general-purpose AI model’ means an AI model, including where such an AI model is trained with a large amount of data using self-supervision at scale, that displays significant generality and is capable of competently performing a wide range of distinct tasks regardless of the way the model is placed on the market and that can be integrated into a variety of downstream systems or applications, except AI models that are used for research, development or prototyping activities before they are placed on the market | Article 3, point (63) |

## For review: found by one extraction only, or quoted differently

These are not in `data/definitions.json`; only definitions both extractions found and quoted alike are.

- TW-01, artificial intelligence: only in first

## Not found in the stored text

Not found means only that the stored files do not define the term: where they are a press release or a status page rather than the instrument's text (the extraction's note says so), that text has to be archived before a later run can look again.

- EU-03: artificial intelligence, AI model, model, high-risk AI system, frontier model, foundation model, generative AI, automated decision system
- OECD-01: artificial intelligence, AI model, model, high-risk AI system, frontier model, foundation model, generative AI, general-purpose AI model, automated decision system
- TW-01: AI system, AI model, model, high-risk AI system, frontier model, foundation model, generative AI, general-purpose AI model, automated decision system

