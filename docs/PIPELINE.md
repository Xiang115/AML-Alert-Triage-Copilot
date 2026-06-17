# Development Pipeline — AML Alert-Triage Copilot

How we go from an empty repo to a filmed demo. **Specific** steps, files, interfaces, and "done when"
gates per phase. Read alongside `CLAUDE.md` (contract/stack), `CONTEXT.md` (vocab), `docs/PRD.md`,
`docs/adr/0001`–`0007`, and `docs/handoff-backend.md`.

Today is **17 Jun 2026**. Golden path must run end-to-end by **23 Jun** (Day 7). Final deadline **26 Jun**.

## Progress tracker

| Phase | What | Owner | Target | Status |
|---|---|---|---|---|
| 0 | Scaffold + shared contract types | A + B | 18 Jun | ✅ |
| 1 | Data foundation (SynthAML features + held-out split) | B | 19 Jun | ✅ |
| 2 | LLM client + knowledge base | B | 19 Jun | ✅ |
| 3 | Triage agent + confidence | B | 20 Jun | ✅ |
| 4 | Verifier agent (the wow) | B | 20 Jun | ✅ (agent; hero-craft in P6) |
| 5 | STR drafter + pipeline orchestrator | B | 21 Jun | ☐ |
| 6 | Hero cases + demo queue + precompute → results.json | B | 21 Jun | ☐ |
| 7 | FastAPI serving (5 endpoints) | B | 22 Jun | ☐ |
| 8 | Eval + metrics.json | B | 22 Jun | ☐ |
| 9 | Frontend console (5 beats) | A | 22 Jun | ☐ |
| 10 | Golden-path lock (end-to-end rehearsal) | A + B | 23 Jun | ☐ |
| 11 | Deck + 7-min script + film | A + B | 26 Jun | ☐ |

**Parallelism:** Person A is unblocked from Day 1 — Phase 0 freezes the contract, then A builds the
whole console against fixture JSON (mock mode) while B builds Phases 1–8. They meet at Phase 9.

## Target file tree (what must exist by Phase 8)

```
/backend
  main.py                     FastAPI app (Phase 7)
  schemas.py                  Pydantic models = the API contract (Phase 0)
  llm.py                      swappable DeepSeek client (Phase 2)
  config.py                   env/model ids/thresholds (Phase 0)
  /agents
    knowledge_base.py         load + select Typology Cards (Phase 2)
    triage.py                 (Phase 3)
    confidence.py             pure compute_confidence (Phase 3)
    verifier.py               adversarial QA (Phase 4)
    str_drafter.py            (Phase 5)
    pipeline.py               orchestrator: retrieve→triage→confidence→verify→draft (Phase 5)
  /data
    synthaml/                 (gitignored CSVs — Phase 1)
    explore_schema.py         one-off header/category dump (Phase 1)
    synthaml_loader.py        raw → AlertFeatures + held-out split (Phase 1)
    alert_features.csv        precomputed per-alert features, 20k rows (Phase 1)
    holdout_alert_ids.json    frozen held-out split (Phase 1)
    hero_cases.json           hand-crafted alerts (Phase 6)
    precompute.py             build tool → results.json (Phase 6)
    results.json              what the API serves (Phase 6)
    metrics.json              (Phase 8)
    typologies/               KB — ALREADY BUILT
  /eval
    evaluate.py               (Phase 8)
  /tests
    test_confidence.py  test_evaluate.py  test_str_drafter.py  test_synthaml_loader.py
  requirements.txt
  .env                        DEEPSEEK_API_KEY (gitignored)
/frontend                     Vite + React + Tailwind (Phase 0, 9)
```

---

## Phase 0 — Scaffold + shared contract (Day 1, both)

**Goal:** lock the wire contract in code so A and B can work in parallel.

**Backend.**
1. `requirements.txt`: `fastapi uvicorn[standard] pydantic python-dotenv openai pandas pytest`.
   (DeepSeek via its OpenAI-compatible endpoint, so the `openai` SDK is the client — ADR/CLAUDE stack.)
2. `backend/schemas.py` — Pydantic v2 models for every entity in `CLAUDE.md` → "API contract":
   `Account, Transaction, Alert, MatchedTypology, Verifier, STRDraft, TriageResult, Decision, Metrics`.
   Internal fields snake_case; emit camelCase via `model_config = ConfigDict(alias_generator=to_camel,
   populate_by_name=True)` and dump with `by_alias=True`. **This file is the single source of the contract.**
3. `backend/config.py` — load `.env`; expose `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`
   (`https://api.deepseek.com/v1`), `MODEL_WORKHORSE` (deepseek-v4-pro), `MODEL_VERIFIER` (deepseek-v4-flash),
   `REVIEW_THRESHOLD` (default 0.6), `RANDOM_SEED`.
4. `backend/main.py` — stub `GET /alerts` returning `[]`; enable CORS for the Vite dev origin.

**Frontend.**
5. `npm create vite@latest frontend -- --template react-ts`; add Tailwind.
6. `frontend/src/types.ts` — TS mirror of `schemas.py` (camelCase).
7. `frontend/src/api.ts` — client with a `MOCK` flag that reads `frontend/src/fixtures/*.json` so A is
   not blocked on the backend.

**Done when:** `uvicorn main:app` (from `/backend`) serves `GET /alerts` in camelCase; frontend renders an
empty queue page; both committed.

## Phase 1 — Data foundation (Day 2, B) — CRITICAL PATH, do before any prompt tuning ✅ DONE

**Reality (after profiling):** alerts are `AlertID, Date, Outcome`; transactions are `AlertID, Timestamp,
Entry(Credit|Debit), Type(Card|Wire|Cash|International), Size` with **median ~829 txns/alert** and
**`Size` normalized (not currency)**; no counterparty/holder/KYC. So real data drives the **accuracy
metric only**; the demo is hand-crafted (see ADR-0005 Phase 1 update). The loader reduces each alert to
an `AlertFeatures` record rather than mapping to display entities.

1. Download to `backend/data/synthaml/` (gitignored). ✅
2. `backend/synthaml_loader.py` (TDD'd pure functions):
   - `aggregate_features(txns) -> DataFrame` — one row/alert: volume, credit/debit, channel mix
     (card/wire/cash/intl), span/dormancy/burst, size mean/std/max, net flow.
   - `stratified_split(labels, holdout_frac, seed) -> (working, holdout)` — stratified on Outcome,
     deterministic by seed.
   - `build(synthaml_dir, out_dir)` — I/O entrypoint: streams the 935 MB once → writes
     `data/alert_features.csv` (committed, 20k rows) + `data/holdout_alert_ids.json` (committed,
     16,000 held-out).
3. `tests/test_synthaml_loader.py` — feature values on a tiny fixture; split disjoint/sized/ratio-
   preserved/deterministic.

**Done when:** ✅ `build` produced `alert_features.csv` (20k rows, 0 NaN) + `holdout_alert_ids.json`
(80%, 0.172 Report ratio in both sets); `pytest` green (15 tests).

## Phase 2 — LLM client + knowledge base (Day 2–3, B)

1. `backend/llm.py`:
   - `complete_json(system: str, user: str, model: str) -> dict` — calls DeepSeek via the OpenAI SDK
     (`base_url=DEEPSEEK_BASE_URL`), **`temperature=0`** (ADR-0003), `response_format` JSON; parse + return.
     One retry on parse failure. Provider/model swappable via `config.py`.
2. `backend/agents/knowledge_base.py`:
   - `load_cards() -> list[Card]` (from `data/typologies/typologies.json`)
   - `select_cards(alert) -> list[Card]` — for the small set, return all 5 and let the model pick; keep
     the hook so it can narrow by `trigger` later. `get_card(code) -> Card`.

**Done when:** a one-off `complete_json` smoke call returns parsed JSON; `load_cards()` returns 5 cards.

## Phase 3 — Triage agent + confidence (Day 3–4, B)

1. `backend/agents/triage.py` — `triage(alert, cards) -> dict` with: `matchedTypology` (code/name/source),
   `firedIndicators` (subset of the card's indicators present in the evidence), `citedTransactionIds`,
   `recommendation` (escalate/dismiss), `explanation`. Prompt embeds the cards' indicators + dataSignals;
   instruct it to cite transactions by id. Use `MODEL_WORKHORSE`.
2. `backend/agents/confidence.py` — **pure** `compute_confidence(fired_count, total_count,
   verifier_flagged) -> float`: `fired/total`, then if `verifier_flagged` cap below `REVIEW_THRESHOLD`
   (ADR-0007). No I/O, no LLM.
3. `tests/test_confidence.py` — 0/N→low, N/N→high, flagged caps below threshold, boundaries.

**Done when:** `triage` on a sampled alert returns a structured call citing real transaction ids;
confidence tests green.

## Phase 4 — Verifier agent (Day 4, B) — the demo wow

1. `backend/agents/verifier.py` — `verify(alert, triage_result, card) -> Verifier`. **Adversarial prompt**
   (ADR-0001): "You are a skeptical QA reviewer. Assume the triage call is wrong. Using the typology's
   distinguishingTest and benignLookalike, decide whether the cited evidence ACTUALLY satisfies the
   typology or could be the benign look-alike." Output `status` (agreed/flagged),
   `agreesWithRecommendation`, `note`. Use the cheaper `MODEL_VERIFIER`. Caller also flags when
   `confidence < REVIEW_THRESHOLD`.

**Done when:** on a benign-look-alike input the verifier returns `flagged` with a note naming the unmet
distinguishing test; on a clear-cut input it returns `agreed`.

## Phase 5 — STR drafter + orchestrator (Day 4–5, B)

1. `backend/agents/str_drafter.py` — `draft_str(alert, triage_result, card) -> STRDraft | None`. Returns
   `None` unless `recommendation == escalate`. Build the structured object (shape in `CLAUDE.md` /
   ADR-0006): subject from `Account`; `citedTransactions` from `citedTransactionIds`; `activitySummary`
   and `groundsForSuspicion` generated using the card's `strNarrativeHints` + `firedIndicators`.
2. `backend/agents/pipeline.py` — `run_triage(alert) -> TriageResult`: `select_cards` → `triage` →
   `compute_confidence` → `verify` → `draft_str`; assemble + return. **Used by both precompute and the
   live endpoint** so they share one code path.
3. `tests/test_str_drafter.py` — all required fields populated; `citedTransactions` matches ids;
   `None` on dismiss.

**Done when:** `run_triage(alert)` returns a complete `TriageResult` end-to-end for one real alert.

## Phase 6 — Hero cases + demo queue + precompute (Day 5, B)

1. **Curate the demo queue** (~10–15) from the Phase 1 *working* set: mostly benign + a few real, each
   illustrating a typology that's evidenceable from real rows — **pass-through, dormant, structuring
   only** (ADR-0005 table). Record the chosen ids.
2. **Hand-craft `hero_cases.json`** (2–3): the verifier-catch case (engineer the margin so the
   distinguishingTest *clearly* fails — ADR-0003) + the **fan-in** and **KYC-mismatch** cases (these
   need counterparty/profile fields SynthAML lacks, so they live here with full fields).
3. `backend/data/precompute.py` — load demo queue + hero cases, run `run_triage` over each, write
   `results.json` (list of `Alert` with embedded `triage`). **Build tool, run manually — not an endpoint.**

**Done when:** `results.json` exists; opening the hero alert shows `verifier.status == flagged`; escalate
alerts carry a populated `strDraft`, dismiss alerts carry `null`.

## Phase 7 — FastAPI serving (Day 5–6, B)

`backend/main.py` loads `results.json` into memory on startup, serves the 5 locked endpoints
(`CLAUDE.md` → API contract):
- `GET /alerts` (+ `?status=`) · `GET /alerts/{alertId}` (account + embedded txns + triage)
- `POST /alerts/{alertId}/triage` — live: calls `pipeline.run_triage`, returns fresh `TriageResult`
- `POST /alerts/{alertId}/decision` — approve/override → update status in an in-memory dict, return Alert
- `GET /metrics` — serve `metrics.json` (Phase 8)
Error shape `{ "error": { "code","message" } }`; dump models `by_alias=True` (camelCase).

**Done when:** all 5 endpoints return contract-shaped camelCase; a decision flips the alert status; live
`/triage` works on at least one alert.

## Phase 8 — Eval + metrics (Day 6, B)

1. `backend/eval/evaluate.py` — take a **stratified ~100–300 sample** of `holdout_alert_ids.json`
   (seeded; ADR-0004), run `run_triage`, compare `recommendation` vs `outcome`. Compute
   `accuracyVsLabels` and `falsePositiveReduction` (definition in ADR-0004). Write `metrics.json` with
   those + the cited `avgReviewTimeBaselineMin` and modeled `avgReviewTimeWithCopilotMin` + sample `n`.
2. `tests/test_evaluate.py` — metric math on fixture predictions (all-right, all-wrong, no-dismissals).

**Done when:** `metrics.json` populated; `GET /metrics` serves it; tests green.

## Phase 9 — Frontend console (Day 3–7 parallel, A)

Build against fixtures from Day 1, switch `api.ts` to live in this phase. Pages (PRD user stories):
- **Alert Queue** — list, `?status` filter, risk/trigger.
- **Alert Detail** — account, transaction table with **runningBalance draining**, embedded triage
  (recommendation + confidence + typology + cited txns highlighted), verifier panel.
- **STR Review** — render the `STRDraft`; only `activitySummary` + `groundsForSuspicion` editable
  (ADR-0006); approve/override → `POST /decision`.
- **Metrics** — the four numbers from `/metrics`.
Triage renders embedded/instant; show the "analyzing…" spinner **only** on the live `/triage` button.

**Done when:** all 5 beats are clickable end-to-end against the running backend.

## Phase 10 — Golden-path lock (Day 7 = 23 Jun, both)

Rehearse the 5 beats off `results.json` start-to-finish (queue → triage+explanation → **verifier
catch** → STR edit/approve → metrics). Fix anything that stalls. **Freeze `results.json` and the
frontend.** Prepare Q&A: live `/triage` on a non-hero alert + the honesty lines from ADR-0004/0005.

**Done when:** the demo runs cleanly with zero manual intervention.

## Phase 11 — Deck, script, film (Day 8–10, both/shared)

Deck + 7-min video script (5 beats + metric slide stating the sample `n` and the FP-reduction
definition) + record off the frozen precomputed results. Roadmap slide = related-account investigation
+ fully-live triage (explicitly out of scope, ADR-0002/guardrails).

---

## Decisions you must NOT relitigate while building

All in `docs/adr/`: adversarial verifier (0001) · cards-not-RAG (0002) · temp-0 + engineered hero
(0003) · sampled held-out accuracy (0004) · three data buckets + typology-reality table (0005) ·
structured `strDraft` object (0006) · computed confidence (0007). If you feel the urge to change one,
update the ADR first, then the code.
