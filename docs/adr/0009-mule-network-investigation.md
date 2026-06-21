# Mule-network investigation is built for the final round, as a hybrid graph + precomputed agent

`CLAUDE.md` and `docs/PRD.md` (*Out of Scope*) explicitly defer related-account / network
investigation and graph visualization to "roadmap slides, not work." This ADR **reverses that for the
final round only**: between the finalist announcement (4 Jul) and the physical final (10 Jul) we build
a **Mule Network** investigation feature (see `CONTEXT.md`) as the single deep feature that raises the
live Technical (30) + Innovation (30) score. The prelim build and its 7-min video stay as-is; the
prelim video pitches this as the headline roadmap item so the final *pays it off* ("we said this was
next — here it is").

**Hybrid, not pure-viz and not live-agent.** A deterministic graph-walk assembles the structure —
accounts are linked by a **shared `counterpartyAccount`** (the **Consolidation Account** multiple
flagged accounts forward into), so there are **no hallucinated edges**. A **precomputed** LLM
*Network Agent* pass then does the reasoning: it assigns each account a **Node Role**
(originator → mule → consolidation account → beneficiary), names the **network-scale Typology**, and
writes the narrative. Structure you can trust; reasoning that earns the word "agentic." Pure
visualization invites "that's a link chart every vendor has — where's the AI?"; a live agent over the
network would break the temp-0 determinism guarantee (ADR-0003) on the filmed/critical path.

**The crafted network does two jobs at once.** ~5 accounts converge on one Consolidation Account:
two already-escalated mules; **one hidden mule that single-alert Triage *dismissed*** (alone it looked
benign — the network adds cross-account evidence Triage never had); and **one benign account the
Network Agent *clears*** (it legitimately pays the same beneficiary). The hidden-mule reveal is the
recall reframe made concrete; the benign-clear proves the graph discriminates rather than colouring
every neighbour red (the Verifier philosophy, extended to networks).

**The hidden mule is a *dismissed Alert*, re-surfaced — not a triage error.** It stays inside the
existing `Alert` model with `disposition=dismiss`. The framing is "Triage was correct within its scope;
single-account view is *structurally* blind to network-distributed laundering." This is the
bulletproof answer to the Q&A landmine on the held-out **recall = 0.0233** number: account-level triage
(and rule-based monitoring) has a recall ceiling that only link-analysis breaks.

**Integrity guardrail: the network is demo-data only and changes no measured number.** It runs on a
hand-crafted cluster (SynthAML has no counterparty identity — see the backend handoff), exactly like
the existing hero cases. The recall reframe is a **talking point, not a metric**: `metrics.json` stays
the honest held-out result. We do **not** fabricate a "network-improved recall." Q&A caveat ready:
same "real or staged?" honesty we already give for hero cases.

**Determinism + seam (ADR-0003, ADR-0008).** Network Agent output (roles, typology, narrative) is
precomputed into a new `backend/data/networks.json`, loaded at startup like `results.json`; graph
layout uses fixed/precomputed coordinates so every take renders identically. New endpoint
`GET /alerts/{alertId}/network` returns the assembled Mule Network (camelCase) — an addition to the
otherwise-locked contract. An optional `POST` live-recompute may mirror the `/triage` spinner-replay
fallback if time allows.

**STR scope unchanged.** Escalating the hidden mule drafts *its own* per-account STRDraft → goAML
export, untouched (`goaml.py` not modified). A consolidated network-level STR is roadmap.

**Demo placement: a new beat 3.5, after the Verifier.** Depth-then-breadth — the Verifier catches a
wrong call on one alert; the network catches the hidden mule across alerts and clears the benign — then
escalate the hidden mule → STR → goAML. Acceptable as a dedicated beat because the final is a live demo
with more room than the prelim's 7-min video (which is why goAML stayed folded into beat 4).

**Cut-line (build order de-risks the demo).** Core = crafted+frozen data → deterministic walk (unit
tested) → precomputed agent pass → endpoint. Polish = the interactive graph view. If time runs short,
degrade gracefully: drop the benign-clear nuance first (→ hidden-mule reveal only), then fall back from
interactive graph to a precomputed static graphic. The deterministic walk + roles is the spine and ships
first; graph viz (frontend long pole) starts as a throwaway spike on day 1 in parallel with data craft.

Rejected: (a) pure visualization — no defensible "AI" story; (b) live network agent — breaks ADR-0003
on camera; (c) never-alerted "lead" surfaced by the network — stronger story but adds a new
non-Alert concept + workflow we can't harden in 6 days (roadmap); (d) network context feeding the Triage
Agent — deepest integration but rewrites the linear pipeline (roadmap); (e) consolidated network STR —
touches `goaml.py` for no demo gain.
