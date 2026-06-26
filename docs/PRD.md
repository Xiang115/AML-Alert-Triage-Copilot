# PRD — AML Alert-Triage Copilot (NexHack 2026, Track 2)

> Domain vocabulary follows `CONTEXT.md`. Decisions reference `docs/adr/0001`–`0007`.
> Hard deadline 26 Jun 2026; golden path must run end-to-end by 23 Jun.

## Problem Statement

A bank AML analyst opens their morning queue to dozens of suspicious-transaction **Alerts**, the
large majority of which are false positives. For each one they must manually pull the account and its
transactions, recall which money-laundering **Typology** it might match, decide **Escalate** or
**Dismiss**, justify the call against regulatory guidance, and — when escalating — hand-write a
**Suspicious Transaction Report (STR)**. It is slow, repetitive, inconsistent between analysts, and the
volume of benign-looking Alerts means real ones risk being rushed. There is no second pair of eyes on
a borderline call until a supervisor reviews it much later.

## Solution

A copilot that triages each Alert for the analyst and keeps the human as the final decision-maker. For
an Alert it: recommends Escalate/Dismiss with a coverage-based **confidence**; explains the call
against a matched **Typology Card** citing the specific transactions; runs an independent
**adversarial Verifier** that challenges the first call and forces human review when the evidence does
not actually satisfy the typology's **Distinguishing Test**; drafts a structured **STRDraft** when the
recommendation is Escalate; and lets the analyst edit and approve, or override. The filmed demo serves
**precomputed** results for reliability, with one live endpoint to prove the pipeline is real.

## User Stories

1. As an AML analyst, I want to see a queue of pending Alerts, so that I can work through my morning caseload.
2. As an AML analyst, I want the queue to filter by status (pending/approved/overridden), so that I can focus on what still needs review.
3. As an AML analyst, I want each queue item to show a risk score and trigger, so that I can sense which Alerts look urgent.
4. As an AML analyst, I want to open an Alert and see the account holder, account type, and opened date, so that I have the customer context.
5. As an AML analyst, I want to see the Alert's transactions with amount, direction, counterparty, channel, and running balance, so that I can read the pattern myself.
6. As an AML analyst, I want the running balance shown per transaction, so that I can see funds draining toward zero (the mule tell).
7. As an AML analyst, I want a recommended disposition (Escalate or Dismiss) for each Alert, so that I have a starting point instead of a blank slate.
8. As an AML analyst, I want a confidence score next to the recommendation, so that I know how strongly the evidence supports it.
9. As an AML analyst, I want the confidence to reflect how many of the typology's red flags actually fired, so that the number is explainable rather than a guess.
10. As an AML analyst, I want the recommendation explained against a named Typology, so that the reasoning is grounded in known laundering patterns.
11. As an AML analyst, I want the explanation to cite the specific transactions that drove it, so that I can verify the evidence quickly.
12. As an AML analyst, I want the matched Typology to show its source (FATF/BNM), so that the explanation is regulator-defensible.
13. As an AML analyst, I want an independent Verifier to challenge the triage call, so that a weak or wrong recommendation is caught before I act.
14. As an AML analyst, I want the Verifier to flag the Alert for human review when the evidence does not satisfy the typology's Distinguishing Test, so that benign look-alikes are not wrongly escalated.
15. As an AML analyst, I want the Verifier to flag low-confidence calls, so that borderline Alerts always reach a human.
16. As an AML analyst, I want to see the Verifier's note explaining its agreement or flag, so that I understand why it pushed back.
17. As an AML analyst, I want a drafted STR when the recommendation is Escalate, so that I do not start the report from scratch.
18. As an AML analyst, I want the STR draft structured into sections (subject, typology, period, activity summary, cited transactions, grounds for suspicion, recommended action), so that it reads like a real regulatory report.
19. As an AML analyst, I want to edit the STR's activity summary and grounds for suspicion, so that I can correct or strengthen the narrative before filing.
20. As an AML analyst, I want the cited transactions pre-populated in the STR, so that I do not re-key transaction details.
21. As an AML analyst, I want to approve an Alert's recommendation, so that I can clear the ones the copilot got right quickly.
22. As an AML analyst, I want to override the recommendation and set my own final disposition, so that I remain the decision-maker.
23. As an AML analyst, I want my decision (approve/override) to update the Alert's status, so that the queue reflects what I have handled.
24. As an AML analyst, I want benign Alerts that superficially resemble a Typology (high-turnover business, salary/rent) to be correctly dismissed, so that I do not waste time on false positives.
25. As a demo presenter, I want the precomputed triage to appear instantly when opening an Alert, so that the filmed flow never stalls or flakes.
26. As a demo presenter, I want a live triage endpoint I can run on demand during Q&A, so that I can prove the pipeline is real, not canned.
27. As a demo presenter, I want a hero Alert where the Verifier visibly catches a wrong call, so that the differentiator lands on camera.
28. As a demo presenter, I want a metrics view showing accuracy and review-time impact, so that I can close with quantified value.
29. As a judge, I want the accuracy number measured on held-out real Alerts, so that I can trust it is not self-graded.
30. As a judge, I want the false-positive-reduction metric defined precisely, so that I can see exactly what is being claimed.
31. As Person B (backend), I want the agent pipeline behind one swappable LLM client, so that the model/provider is a config change.
32. As Person B (backend), I want an offline precompute script that writes results.json, so that the backend serves demo results without live latency.
33. As Person B (backend), I want the held-out eval slice carved before any prompt tuning, so that the accuracy metric measures generalization, not memorization.
34. As Person A (frontend), I want a stable camelCase API contract, so that I can build the console without backend churn.

## Implementation Decisions

**Architecture (per CLAUDE.md, ADR-0003).** Backend serves **precomputed** `TriageResult`s loaded from
`results.json` on startup. A separate offline **precompute script** runs the pipeline over the demo
queue and writes that file — it is a build tool, not an endpoint. One live endpoint
(`POST /alerts/{alertId}/triage`) runs the pipeline on demand for Q&A. Pipeline is **plain linear
Python**: retrieve Typology Card → triage → verify → draft. No LangGraph/LangChain.

**LLM client (deep module).** Single provider-agnostic wrapper over the **DeepSeek API** (OpenAI-compatible
endpoint), **temperature 0** across the pipeline (ADR-0003). **DeepSeek V4 Pro** for triage + STR drafting;
**DeepSeek V4 Flash** for the Verifier. Interface roughly: `complete(prompt, model, schema) -> parsed`.

**Knowledge base (deep module, ADR-0002).** Loads the curated **Typology Cards** from
`backend/data/typologies/typologies.json` and selects the relevant card(s) for an Alert. No embeddings,
no PDF RAG; the card set is small enough to pass into the prompt. The large off-topic PDFs are not on
the demo path; `fatf_recommendations_2012` and `financial_fraud_alerts` remain as citation anchors only.

**Triage agent.** Given an Alert (account + transactions) and candidate Typology Card(s), the LLM
returns: `matchedTypology`, the list of card indicators that fired, `citedTransactionIds`,
`recommendation` (escalate/dismiss), and `explanation`.

**Verifier agent (adversarial, ADR-0001).** Given the triage call plus the matched card's
`distinguishingTest` and `benignLookalike`, the Verifier takes a skeptical QA role — it assumes the
call may be wrong and tests whether the evidence actually satisfies the Distinguishing Test or could be
the Benign Look-alike. Emits `verifier: { status: agreed|flagged, agreesWithRecommendation, note }`.
Flags on disagreement **or** confidence below the human-review threshold. An optional deterministic
rules-based floor may back the LLM Verifier if reproducibility proves flaky (built only if time allows).

**Confidence computation (deep, pure module, ADR-0007).** `confidence` is **computed**, not
self-reported: the fraction of the matched card's indicators that fired, capped below the human-review
threshold when the Verifier flags a **dismiss** (a flagged escalate keeps its coverage — the disagreement,
not a depressed score, forces review). Interface: `compute_confidence(fired_count, total_count, recommendation, verifier_flagged) -> float`.
The human-review threshold (e.g. ~0.6) is a single configurable constant, finalized when `evaluate.py` is built.

**STR drafter (ADR-0006).** When the recommendation is Escalate, produces a **structured `STRDraft`
object** (not a freeform string). Shape:

```jsonc
"strDraft": {                          // null unless recommendation == escalate
  "reportDate", "reportingInstitution",
  "subject": { "accountId","holderName","accountType","openedAt" },
  "typology": { "code","name","source" },
  "period": { "from","to" },
  "activitySummary": "...",            // editable in UI
  "citedTransactions": [ { "transactionId","timestamp","amount","currency","counterpartyName","runningBalance" } ],
  "groundsForSuspicion": [ "..." ],    // editable list
  "recommendedAction": "..."
}
```

`Decision.editedStrDraft` mirrors the same shape. On camera only `activitySummary` and
`groundsForSuspicion` are richly editable; `subject` and `citedTransactions` render populated/read-only.

**Pipeline orchestrator.** Coordinates retrieve → triage → verify → draft and assembles the
`TriageResult`. Used by both the precompute script and the live `/triage` endpoint so they share one
code path.

**Data — three buckets (ADR-0005).** SynthAML normalized into `Alert`/`Transaction`/`Account`. (1) A
curated **demo queue** of ~10–15 real SynthAML rows (mostly false positives, a few real), each mapping
to one Typology Card. (2) 2–3 **hand-crafted hero cases** — the Verifier-catch case plus 1–2 Benign
Look-alikes — used only for narrative, never counted in accuracy. (3) A large **held-out eval slice**,
never seen during prompt tuning and never shown in the demo. The held-out split is carved before any
tuning (Person B's first data task).

**API contract (locked, camelCase).** `GET /alerts` (optional `?status=`), `GET /alerts/{alertId}`
(account + embedded transactions + embedded triage), `POST /alerts/{alertId}/triage` (live run, Q&A
only), `POST /alerts/{alertId}/decision` (approve/override → updated Alert), `GET /metrics`. Error shape
`{ "error": { "code","message" } }` with standard HTTP codes. Internal snake_case mapped to camelCase at
the boundary.

**Decision persistence.** In-memory dict for the session (trivially reversible to a decisions file).

**Metrics (ADR-0004).** `accuracyVsLabels` measured over the held-out slice (% agreement of
`recommendation` vs Report/Dismiss label). `falsePositiveReduction` defined as: of the Alerts the
copilot recommends Dismiss, the share truly benign (label = Dismiss) — stated on the slide.
`avgReviewTimeBaselineMin` is a cited industry figure (labeled an assumption);
`avgReviewTimeWithCopilotMin` a conservative modeled estimate; time-saved presented as illustrative.

**Frontend.** React (Vite) + Tailwind console: Alert Queue, Alert Detail (account + transactions +
embedded triage + verifier), STR Review (structured editor), Metrics. Triage renders embedded/instant
in the filmed flow; an "analyzing…" spinner appears only on the live `/triage` run.

## Testing Decisions

Tests cover **external behavior of the deterministic modules only** — given inputs, assert the returned
values/shape — not internal implementation details, and not the LLM-calling agents (whose output is
non-deterministic). The LLM agents (triage, verifier, STR drafter) get at most **one optional
integration smoke test** driven by a recorded fixture, asserting the pipeline produces a well-formed
`TriageResult`; they are not unit-tested.

Unit tests will be written for these four modules:

1. **Confidence computation** — `compute_confidence(fired_count, total_count, verifier_flagged)`: full
   coverage → high value; zero coverage → low; a flagged Verifier caps the result below the human-review
   threshold regardless of coverage; boundary values (0 of N, N of N). The most valuable test target —
   it backs every on-screen confidence number.
2. **Eval metrics** — given a fixed set of predictions and labels, assert `accuracyVsLabels` and the
   precisely-defined `falsePositiveReduction` are computed correctly, including edge cases (all correct,
   all wrong, no dismissals). Defends the metric slide under judging.
3. **STRDraft assembly** — given an escalate triage result + Alert + matched card, assert the `STRDraft`
   object has every required field populated, `citedTransactions` matches `citedTransactionIds`, and the
   object is `null` when the recommendation is Dismiss.
4. **SynthAML normalization** — given raw SynthAML rows, assert correct mapping to
   `Alert`/`Transaction`/`Account` (including `runningBalance` and `direction`) and that the three-bucket
   split is disjoint (no held-out row leaks into the demo queue).

No prior-art tests exist yet (pre-implementation repo); these establish the pattern. Use plain `pytest`.

## Out of Scope

- Training or fine-tuning any ML model — triage is an LLM call, not a classifier.
- A real RAG stack / vector index over the source PDFs (ADR-0002).
- Fully-live triage on every Alert (only the hero/Q&A path runs live; the demo is precomputed).
- Related-account / network investigation across many accounts, and graph visualization (roadmap slide).
- Real banking integrations, full case-management platform, enterprise auth, durable database.
- Per-field STR editing beyond `activitySummary` and `groundsForSuspicion` for the demo.
- Anything outside the 5-beat golden path.

## Further Notes

- **Critical path:** the SynthAML data work (download, curate the ~10–15 queue, carve the held-out
  split, craft the hero cases) blocks both the demo and the accuracy metric — it is Person B's first task.
- **KB content** in `typologies.json` still needs the AML-expert pass (verify indicators, `source`
  sections, and the RM25,000 CTR threshold).
- **Two numbers to finalize during build:** the human-review confidence threshold, and the cited
  baseline review-time source.
- **Work split:** Person A — frontend console + integration + demo recording; Person B — agent pipeline
  + FastAPI + precompute + eval. Shared last 2 days — deck + 7-min video script + recording.
- Decisions are recorded in `docs/adr/0001`–`0007`; domain language in `CONTEXT.md`.
