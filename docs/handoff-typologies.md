# Handoff — Typology Cards (scoped task)

**Owner:** (you)
**Date:** 2026-06-18
**Deadline reminder:** golden path must run end-to-end by **23 Jun**, demo **26 Jun**.

## Your scope — read this twice

You own **`backend/data/typologies/` ONLY**. That is two files:

- `backend/data/typologies/typologies.json` — the curated AML typology cards
- `backend/data/typologies/README.md` — the schema doc for those cards

**Do NOT touch anything else in the repo.** No `agents/`, no `main.py`, no
`precompute.py`, no `synthaml_loader.py`, no frontend, no `docs/adr/`, no
`results.json`. If a change you want needs a file outside this folder, **stop
and ping me** — don't edit it yourself.

Why so strict: these cards are the one piece of the knowledge base that is
self-contained and can't break the pipeline as long as the JSON stays valid and
the schema/field names don't change. Everything else has live dependencies.

## What this file is (context)

`typologies.json` is the **knowledge base** for the triage + verifier agents. It
is a tiny set of **hand-authored typology cards** — NOT a RAG index over the
PDFs (see `docs/adr/0002`). Each card doubles as the **verifier's checklist**:
its `distinguishingTest` is exactly what the verifier challenges the triage call
against, and its `benignLookalike` is the innocent pattern triage must not
confuse it with.

There are 5 cards today:

| code | name |
|---|---|
| `PT-01` | Pass-through / Rapid Movement |
| `FI-01` | Fan-in / Fan-out (Consolidation) |
| `ST-01` | Structuring / Smurfing |
| `DA-01` | Dormant-then-Active |
| `KYC-01` | KYC Profile Mismatch |

## The card schema — do NOT rename or remove fields

Every card MUST keep exactly these keys (the agents read them by name; renaming
one silently breaks triage/verifier/STR):

`code`, `name`, `source`, `definition`, `indicators` (array),
`dataSignals` (array), `benignLookalike`, `distinguishingTest`,
`typicalDisposition` (`escalate` | `dismiss`), `strNarrativeHints` (array).

Field meanings are in `README.md` — read it before editing. The most important
ones to get right:

- **`dataSignals`** — the indicators expressed against our actual
  `Transaction` / `Account` fields (`runningBalance`, `direction`, `amount`,
  `channel`, `counterpartyName`…). This is what makes a card *checkable* against
  data. Keep them concrete and field-accurate.
- **`distinguishingTest`** — the verifier's core check. Must clearly separate the
  typology from its `benignLookalike`. This is the demo "wow" — make it sharp.

## What you can usefully work on (all inside the two files)

Pick from these — none require touching code:

1. **Sharpen `distinguishingTest` strings** so the typology vs. benign look-alike
   line is crisp. This directly improves the verifier demo beat.
2. **Tighten `source` citations** — verify FATF/BNM section numbers against the
   PDFs in `../knowledge_base/raw_pdfs/` and make `source` strings accurate
   (currently document-level; section numbers are a "if time allows" TODO).
3. **Confirm the RM25,000 CTR threshold** is still current (BNM) — it anchors
   `ST-01`. (Already marked VERIFIED in the JSON `meta`; double-check.)
4. **Improve `indicators` / `dataSignals` / `strNarrativeHints`** wording for
   clarity and field-accuracy.
5. Keep `README.md` in sync if you change the schema doc — but **don't change the
   schema itself** without pinging me.

## Hard rules

- **Valid JSON, always.** After any edit, the file must still parse. Quick check:
  `python -m json.tool backend/data/typologies/typologies.json` (should print the
  file, not an error).
- **Don't add or remove cards** without asking — the demo hero cases are mapped
  to these 5 codes elsewhere in the pipeline. Adding a card is fine in principle
  but it has downstream impact, so coordinate first.
- **Don't change `code` values** (`PT-01`, etc.) — they're referenced by ID
  across the system.
- **No edits outside `backend/data/typologies/`.** If you think you need one,
  message me instead.
- Match the existing tone/structure of the cards. Don't over-engineer — we're a
  two-person team on a deadline.

## Before you say "done"

1. `python -m json.tool backend/data/typologies/typologies.json` parses clean.
2. All 5 cards still have all 10 schema fields, same `code` values.
3. `git status` shows changes **only** under `backend/data/typologies/`.
4. Summarize what you changed and why, and ping me to review before merge.
