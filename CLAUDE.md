# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An **AI copilot that helps a bank AML analyst triage suspicious-transaction alerts** (NexHack 2026, Track 2). For each alert the pipeline: recommends Escalate/Dismiss with a confidence score, explains the call against money-laundering typologies (FATF/BNM), runs a **second "verifier" agent** that challenges the first agent, drafts a Suspicious Transaction Report (STR), and lets the analyst approve/override.

**This is an LLM/agent system. We do NOT train any ML model.** "Triage" = an LLM call, not a classifier.

## Current state

The repo is **pre-implementation**. Only the curated knowledge base lives here so far:
`backend/data/knowledge_base/raw_pdfs/` (FATF recommendations, BNM/financial-integrity guidance, fraud/typology PDFs). There is no `package.json`, no Python source, and no build/test/lint tooling yet — when you scaffold, follow the structure and contract below. `work/` is gitignored (scratch space).

## Hard constraints (these shape every decision)

- **Deadline 26 Jun 2026; golden path must run end-to-end by 23 Jun.** Bias toward the simplest thing that demos.
- **Demo-first:** the filmed demo runs off **precomputed results** so it never flakes. Do not put live LLM latency on the demo's critical path.
- Two-person team. Keep it simple and demoable — no over-engineering. Don't add anything outside the 5-beat golden path.

## Architecture (locked — decision "b")

The backend serves **precomputed triage results** for the demo (instant, reliable), plus **one live endpoint** to prove it's real during Q&A:

- An **offline precompute script** (`backend/data/precompute.py`) runs the full agent pipeline over the dataset and writes `results.json`. This is a **build tool, not an API endpoint** — run it manually; the backend never invokes it at request time.
- **FastAPI loads `results.json` on startup** and serves embedded triage results from memory.
- `POST /alerts/{id}/triage` is the **only** endpoint that runs the pipeline live (Q&A demonstration only).

**Pipeline is plain linear Python**, no framework: `retrieve typology → triage → verify → draft`. No LangGraph/LangChain — too much overhead for a linear pipeline under deadline.

```
agents/knowledge_base.py   → retrieve relevant FATF/BNM typology context (tiny Chroma/FAISS, NOT a real RAG stack)
agents/triage.py           → Escalate/Dismiss + confidence + explanation + cited transactions
agents/verifier.py         → independent second-pass; agrees or flags for human review (the demo "wow")
agents/str_drafter.py      → drafts STR, only when recommendation is escalate
```

## Tech stack (locked)

- **Backend/agents:** Python + FastAPI.
- **LLM:** Gemini API — a capable Gemini model as workhorse (triage + STR drafting); a cheaper/faster Gemini model for the verifier. **Wrap the call behind one swappable client** (Gemini exposes an OpenAI-compatible endpoint) so the model/provider is a config change, not a code change. Use context/prompt caching for the reused typology context.
- **Frontend:** React (Vite) + Tailwind — a polished analyst console.
- **Data:** SynthAML primary (alerts + transactions + Report/Dismiss labels). Backups: SAML-D, IBM-AML.

## Intended repo structure

```
/backend
  /agents        triage.py, verifier.py, str_drafter.py, knowledge_base.py
  /data          synthaml_loader.py, precompute.py, results.json, typologies/
                 knowledge_base/raw_pdfs/   (already present)
  /eval          evaluate.py  (accuracy vs labels + time-saved metric)
  main.py        FastAPI app (loads results.json on startup)
/frontend        Vite + React + Tailwind
/docs            project brief, plan
```

## API contract (locked)

**Wire format is camelCase JSON.** If internal Python uses snake_case, map at the boundary.

```
GET  /alerts                    queue; optional ?status=pending; no pagination
GET  /alerts/{alertId}          detail: account + embedded transactions + embedded triage
POST /alerts/{alertId}/triage   LIVE pipeline run; returns a fresh TriageResult (Q&A only)
POST /alerts/{alertId}/decision approve/override; returns the updated Alert
GET  /metrics                   numbers for the metric slide / dashboard
```

Core shapes (see `/init` brief / `outputs/nexhack-architecture.md` for full field lists):
- **Alert** embeds its `triage` (a TriageResult) and references `transactionIds`. `status`: `pending|approved|overridden`.
- **TriageResult**: `recommendation` (`escalate|dismiss`), `confidence` (0–1), `explanation`, `matchedTypology`, `citedTransactionIds`, nested `verifier` (`status: agreed|flagged`), and `strDraft` — a **structured `STRDraft` object, null unless escalate** (see ADR-0006).
- **STRDraft** (object): `reportDate`, `reportingInstitution`, `subject{accountId,holderName,accountType,openedAt}`, `typology{code,name,source}`, `period{from,to}`, `activitySummary` (editable), `citedTransactions[]` (read-only in demo), `groundsForSuspicion[]` (editable), `recommendedAction`.
- **Transaction**: `runningBalance` is the **key mule tell** — show it draining to ~0. `direction`: `inbound|outbound`.
- **Decision**: analyst `action` (`approve|override`) + `finalDisposition` + optional `editedStrDraft` (same `STRDraft` shape).
- Error shape: `{ "error": { "code", "message" } }` with standard HTTP codes — apply consistently.

> Note: `outputs/nexhack-architecture.md` is an **earlier exploratory draft** with more granular endpoints (`/analyze`, `/verify`, `/draft-str`, `/finalize`) and snake_case fields. The contract above **supersedes it** — those steps are collapsed into the precompute pipeline + the single live `/triage` endpoint.

## Demo golden path (the 5 beats — build only these)

1. Analyst alert queue — the pain (mostly false positives).
2. Open an alert → triage decision + confidence + typology-grounded explanation citing specific transactions.
3. The **verifier catches a wrong call** on a crafted hero case → forces human review. (The wow.)
4. AI drafts the STR → analyst edits & approves.
5. Metric slide: accuracy % + review-time cut on held-out SynthAML alerts.

## Typologies to encode

Each hero case embodies one: pass-through/rapid-movement · fan-in/fan-out (scam-victim consolidation) · structuring/smurfing · dormant-then-active · KYC profile mismatch. **Craft some benign cases that look superficially similar** (high-turnover business, salary/rent) so triage + verifier have to discriminate.

## Guardrails

- DO keep the pipeline debuggable and provider-agnostic (one swappable LLM client).
- DON'T add features outside the 5-beat golden path — related-account investigation, graph visualization, and fully-live-on-every-alert triage are **roadmap slides**, not work.
- DON'T let RAG, graph viz, or live latency eat the timeline.

## Decisions captured in docs

Resolved decisions live in ADRs; domain vocabulary in `CONTEXT.md`. Read these before building:
- `docs/adr/0001` — Verifier is an **adversarial QA** agent (the demo wow), grounded on each card's `distinguishingTest`.
- `docs/adr/0002` — KB is **curated typology cards** (`backend/data/typologies/`), **not PDF RAG**.
- `docs/adr/0003` — Demo determinism: temp 0 pipeline; hero case engineered + spinner-replay fallback.
- `docs/adr/0004` — Metrics: only `accuracyVsLabels` is measured (held-out); time numbers are cited/modeled.
- `docs/adr/0005` — Data is **three buckets**: curated demo queue (~10–15) · hand-crafted hero cases · untouched held-out eval slice.
- `docs/adr/0006` — `strDraft` is a **structured `STRDraft` object** (contract change from string); only `activitySummary` + `groundsForSuspicion` editable on camera.
- `docs/adr/0007` — `confidence` is **computed from indicator coverage**, not self-reported by the LLM; verifier flag caps it below the review threshold.

## Still open (minor)

- Triage delivery: embedded for the filmed flow; spinner only on the live `/triage` run (per ADR-0003).
- Decision persistence: in-memory dict for the session (vs. a decisions file) — leaning in-memory; trivially reversible.

## Work split

- **Person A:** React console + integration + demo recording.
- **Person B:** agent pipeline + FastAPI + precompute + eval/metric.
