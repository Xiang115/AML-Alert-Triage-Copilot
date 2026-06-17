# Handoff — Backend implementation (Person B), AML Alert-Triage Copilot

Repo: `C:\Users\gohki\nexhack-track2-architecture` · branch `main` @ `62c873f`. NexHack 2026 Track 2.
Deadline 26 Jun 2026; golden path end-to-end by 23 Jun. Two-person team; you are **Person B**
(Python: agent pipeline + FastAPI + precompute + eval). All design is **resolved** — this session was
planning only; **no backend code exists yet** (only the typology KB + docs).

## Read these first (don't re-derive — they're authoritative)

- `CLAUDE.md` — stack (Gemini API), locked camelCase API contract, intended repo structure, ADR index.
- `CONTEXT.md` — domain glossary. Use these exact terms (Triage, adversarial Verifier, Typology Card,
  Distinguishing Test, Disposition, STRDraft).
- `docs/PRD.md` — problem, user stories, module breakdown, **testing plan**.
- `docs/adr/0001`–`0007` — the seven locked decisions. Each is one paragraph; read all seven.
- `backend/data/typologies/typologies.json` + `README.md` — the knowledge base (already built).

## Your build order (critical path)

1. **Get the data.** SynthAML from Figshare (see `CLAUDE.md` data line for DOI). The transactions
   file is a **separate 935 MB item**: `synthetic_transactions.csv` →
   `https://ndownloader.figshare.com/files/39841711`; alerts = `synthetic_alerts.csv`. Put both in
   `backend/data/synthaml/` (already gitignored — never commit them).
2. **Inspect real headers FIRST.** Print the actual CSV columns + the alert↔transaction join key + the
   category values of `entry type` / `transaction type`. The contract's `Transaction` schema is
   idealized; reconcile before writing the loader. Field mapping + what's derivable is in **ADR-0005**
   (runningBalance computed, direction from entry type, counterparty/KYC absent → synthesized).
3. **Carve the held-out split BEFORE any prompt tuning** (ADR-0005). Stratify to preserve the ~17%
   reported ratio. This is the first data task or the accuracy number is meaningless.
4. **`synthaml_loader.py`** — raw CSVs → `Alert`/`Transaction`/`Account` + the three-bucket split.
   Unit-tested (see PRD Testing Decisions).
5. **LLM client** — one swappable wrapper over Gemini (OpenAI-compat endpoint), **temperature 0**
   (ADR-0003).
6. **Pipeline** `agents/`: knowledge_base → triage → verifier → str_drafter, plus a pure
   `compute_confidence` (ADR-0007) and an orchestrator shared by precompute + the live endpoint.
   Verifier is **adversarial**, graded on the matched card's `distinguishingTest` (ADR-0001).
7. **`precompute.py`** (build tool, not an endpoint) → `results.json` over the curated demo queue.
8. **`main.py`** FastAPI — loads `results.json` on startup, serves the 5 contract endpoints, in-memory
   decision store, snake→camel at the boundary.
9. **`eval/evaluate.py`** — accuracy + FP reduction on a **stratified ~100–300 sample** of held-out
   (ADR-0004). Unit-tested.

## Gotchas already decided — do NOT relitigate

- **Only 3 of 5 typologies come from real rows** (pass-through, dormant, structuring). **Fan-in/fan-out
  and KYC-mismatch must be hand-crafted hero cases** — SynthAML lacks counterparty identity + customer
  profile. Table in ADR-0005.
- **No PDF RAG.** KB is the JSON cards; pass them into the prompt. The big PDFs are off the demo path.
- **Confidence is computed, not LLM-self-reported** (ADR-0007).
- **`strDraft` is a structured object, not a string** (ADR-0006) — the contract changed; build to the
  object shape in CLAUDE.md.
- **Demo determinism** (ADR-0003): temp 0; the hero verifier-catch case is engineered with margin;
  spinner-replay is the on-camera fallback.

## Tests to write (PRD Testing Decisions, plain pytest)

Deterministic units only: `compute_confidence`, eval metrics, STRDraft assembly, SynthAML
normalization. LLM agents get at most one fixture-driven smoke test — not unit-tested.

## Still open (minor, decide while building)

- Human-review confidence threshold value (~0.6) — fix in `evaluate.py`.
- Cited baseline review-time source for the metric slide.
- Decision persistence: in-memory dict is fine.
- Optional rules-based floor under the LLM verifier (only if reproducibility proves flaky).

## Suggested skills for the next session

- `superpowers:test-driven-development` (or `tdd`) — for the 4 deterministic modules.
- `superpowers:executing-plans` / `subagent-driven-development` — PRD → implementation.
- `safehood-git-flow` — for commits/PRs (adapted here: branch `type/short-desc`, squash-merge,
  `Co-Authored-By: Claude Opus 4.8`, STOP before merge). main is at `62c873f`.
- `claude-api` — when wiring the Gemini client / model IDs / caching.

Not started: anything in `/frontend` (Person A). Nothing is blocked except by the data download (step 1).
