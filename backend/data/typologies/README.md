# Knowledge Base — Curated Typology Cards

This is the AML knowledge base for the triage + verifier agents. It is **a tiny set of
hand-authored typology cards** (`typologies.json`), not a RAG index over the source PDFs.
See `docs/adr/0002-knowledge-base-curated-typology-cards.md` for why.

## Why cards, not PDF RAG

- The demo encodes 5 transaction-pattern typologies. The raw PDFs in `../knowledge_base/raw_pdfs/`
  are big thematic FATF reports (proliferation financing, terrorist financing, CSAE, the 40
  Recommendations) — they are **not** a catalog of these 5 typologies. Embedding them surfaces
  off-topic text and is non-deterministic on the demo path.
- Cards are tiny, deterministic, demo-safe, and they double as the **verifier's checklist**
  (`distinguishingTest` is exactly what the verifier challenges the triage call against).

## Card schema (per entry in `typologies.json`)

| Field | Purpose |
|---|---|
| `code`, `name` | Stable id + label. `code` is what `matchedTypology.code` in the API returns. |
| `source` | Citation anchor for the explanation ("per FATF R.20 / BNM AML/CFT"). |
| `definition` | One-line plain-language description for the analyst. |
| `indicators` | Human-readable red flags the triage agent cites. |
| `dataSignals` | The same flags expressed against our **Transaction/Account fields** (runningBalance, direction, amount, channel…). This is what makes a card *checkable* against real data. |
| `benignLookalike` | The superficially-similar innocent pattern (high-turnover business, salary/rent). |
| `distinguishingTest` | **The verifier's core check** — how to tell the typology from its benign look-alike. |
| `typicalDisposition` | Prior (escalate/dismiss) — not a hard rule, just a default. |
| `strNarrativeHints` | Bullets the STR drafter uses to structure the narrative. |

## How the agents use it

1. **Retrieve** (`agents/knowledge_base.py`): load `typologies.json` once; select the relevant
   card(s). Selection is trivial — match on the alert `trigger` / keyword, or pass *all* cards
   (the set is small enough to fit in the prompt and let the model pick). **No embeddings needed.**
2. **Triage** (`agents/triage.py`): given the alert + transactions + candidate card(s), the model
   picks `matchedTypology`, cites `citedTransactionIds` against the card's `indicators`/`dataSignals`,
   and outputs `recommendation` + `confidence` + `explanation`.
3. **Verify** (`agents/verifier.py`): adversarial QA role. Given the triage call + the matched card's
   `distinguishingTest` + `benignLookalike`, it tries to *break* the call — does the evidence actually
   satisfy the distinguishing test, or could this be the benign look-alike? Emits `agreed` / `flagged`.
4. **Draft** (`agents/str_drafter.py`): uses `strNarrativeHints` + `source` to structure the STR.

## The raw PDFs

Keep `fatf_recommendations_2012.pdf` and `financial_fraud_alerts.pdf` only as **citation anchors**
(so `source` strings are real). The large off-topic PDFs (proliferation 45 MB, CSAE, TF) are **not on
the demo path** — do not embed them. They can stay in the repo as "we considered the broader FATF
corpus" colour for the deck, nothing more.

## To verify before the demo

- Confirm the **RM25,000** CTR cash threshold is current (BNM) — it anchors ST-01.
- Tighten `source` section numbers against the actual PDFs if time allows.
