# The Queue Agent autonomously clears dismisses under a deterministic, audited policy — never escalations

NexHack's main theme is **"Building Autonomous AI Workforce."** The copilot as built is *reactive*: the
analyst opens Alerts one at a time and the agent reasons on demand. That under-hits the theme and leaves
the headline operational pain — the 90%+ false-positive noise an analyst hand-clears every morning —
still entirely manual. This ADR adds a **Queue Agent** (see `CONTEXT.md`) that works the whole queue
**unattended** and routes each Alert, lifting the product from "copilot you drive" to "autonomous analyst
that escalates exceptions to a human."

This **reverses**, in a bounded way, the "the human always decides / decision support, not automated
decisioning" line that the README, PRD, and the commercial moat all lean on — hence this ADR.

**Decision: autonomy on the dismiss side, a hard human gate on the escalate side.** The Queue Agent may
**auto-clear (dismiss)** an Alert without a human, but **never auto-escalates and never auto-files**.
Everything heading toward an STR — every escalation, every Verifier flag, every low-confidence dismiss —
routes to `needsReview` for human sign-off. The human-in-the-loop accountability that makes the product
defensible to a regulator stays exactly where the regulator demands it.

**Why this is the safe cut — AML error cost is asymmetric.** Auto-*dismissing* a true launderer is the
catastrophic error; auto-*escalating* a benign is merely wasted review time. The launderers most likely
to be wrongly dismissed are exactly the **Verifier-flagged / low-confidence** ones — which the
**Auto-Clear Policy** refuses to clear. So the policy claims autonomy only over the high-confidence,
verifier-agreed *benign* noise that is the actual pain, and leaves every uncertain call to a human.

**The Auto-Clear Policy is deterministic, not an LLM.** It fires only when
`recommendation=dismiss AND confidence ≥ AUTO_CLEAR_THRESHOLD AND verifier=agreed` — a pure, unit-tested
function over the already-precomputed triage results (like `confidence.py`). This is a feature, not a
limitation: it cannot flake on camera (ADR-0003), it is trivially auditable, and "our auto-clear criteria
are an explicit, configurable policy" is *more* defensible to a compliance judge than "an AI decided to
close it." The "agentic" credit comes from the Triage + Verifier reasoning the policy sits on top of, plus
a precomputed **Shift Briefing** narrative (the one LLM touch, precomputed so it carries no demo latency).

**The audit trail becomes the accountability record for autonomous action.** Today `/audit` is empty
until a human acts. Every auto-clear now writes an `autoClear` audit entry **at precompute time** (AI
recommendation, confidence, verifier status), so the trail opens *populated* and the institution can
replay exactly what the agent did unattended. Auto-clear without this record is reckless; with it — plus
the **Auto-Cleared** tab where the analyst samples what was cleared — it is a real AML
"alert-hibernation with QA" workflow.

**The metric stays honest (ADR-0004).** The feature is measured, not asserted: `evaluate.py` applies the
Auto-Clear Policy to the held-out predictions and reports **auto-cleared share** (fraction of the queue
handled unattended) and **auto-clear precision** (of auto-cleared Alerts, fraction truly benign). Because
the policy is a strict subset of "dismiss," its precision *can* exceed the `falsePositiveReduction`
figure. We report the measured reality, not the aspiration. **Measured (n=60 held-out, cost-sensitive):
autoClearedShare 90%, autoClearPrecision 87%.** On this amount-less data the confidence+verifier gate did
not bind — the policy cleared *every* confident dismiss — so precision *equals* `falsePositiveReduction`
(87%) rather than exceeding it. 87% precision means **13% of auto-cleared Alerts were actually Reports** —
the recall ceiling (recall 30%), which is why auto-clear is paired with human sampling of the Auto-Cleared
lane and answered structurally by the Mule-Network roadmap. The held-out features are aggregated and
amount-less (ADR-0005), so these are a conservative floor, not the production ceiling.

**Lead the autonomy headline with the held-out number, never the demo queue.** The curated demo queue is
*detection-heavy by design* (crafted to exercise typology match -> STR -> goAML), so the Queue Agent
auto-clears only the provably-clean benigns on it (~3 of 16). That is **presented as conservatism**
("even on a hard, escalation-heavy crafted queue it clears only the clean ones"), not as the headline
volume. The compelling, honest autonomy figure is `autoClearedShare` measured on the **held-out** slice
(~83% benign base rate); the demo queue proves *safety*, the held-out number proves *workload*.

**This restores the Mule-Network roadmap arc (ADR-0009).** The residual risk of auto-clear is a
network-distributed "hidden mule" that looks benign account-by-account — precisely the structural blind
spot Mule-Network Investigation targets. So the prelim ships the Queue Agent and still pitches
Mule-Network as the defensible "what's next."

**Demo placement: a new beat 1.** The demo opens on the worked queue — *"the agent processed 250
overnight, auto-cleared 180, here are the 20 that need me"* (Shift Briefing) — then drills into a
`needsReview` Alert for the existing Triage → Verifier → STR → goAML beats. The autonomous-workforce
story frames the whole demo instead of being bolted on.

**Consequences.** New `backend/agents/queue_agent.py` (pure policy + briefing assembly); `routing` on the
Alert and a `ShiftBriefing` shape in `schemas.py`; `AUTO_CLEAR_THRESHOLD` in `config.py`; `precompute.py`
assigns routing, seeds the audit trail, and writes the briefing; `main.py` loads the audit seed at
startup, serves the briefing, and supports `?routing=`; `evaluate.py` + `metrics.json` gain the two
auto-clear numbers; the frontend gains a Shift Briefing banner, routing lanes in the queue, and an
Auto-Cleared tab. Regenerating `results.json` requires the usual re-sync (hero-case check → fixture sync
→ re-eval).

**Rejected.** (a) *Auto-prepare only* — the agent pre-works but a human still dispositions every Alert:
zero moat risk but the autonomy claim is hollow ("it just sorts my queue"). (b) *Full auto-disposition*
incl. auto-escalate/auto-file: maximally on-theme but breaks the human-in-the-loop moat — a compliance
judge kills it. (c) *LLM orchestrator agent* that reasons about routing per Alert: stronger "agent
orchestration" branding but non-deterministic on camera (ADR-0003) and harder to defend than a
transparent rule. (d) *A learned auto-clear threshold*: reintroduces training/model-risk governance we
deliberately avoid — the threshold is a single configured, disclosed constant instead.
