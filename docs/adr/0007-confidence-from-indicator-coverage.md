# Confidence is computed from indicator coverage, not self-reported by the LLM

`TriageResult.confidence` (0-1) is computed, not asked of the model. The LLM does the grounded part it
is good at — deciding which of the matched typology card's indicators are actually present in the
evidence — and `confidence` measures **support for the chosen recommendation**, capped when the
Verifier flags.

Refinement (Phase 3): confidence is **recommendation-aware**, not raw coverage. Let
`coverage = fired/total`. For an **escalate**, `support = coverage` (more red flags → more confident).
For a **dismiss**, `support = 1 - coverage` (a clean dismiss fires no indicators yet is *high*
confidence — raw coverage would wrongly report ~0). A `flagged` verifier caps support below the
human-review threshold. Implemented as the pure `compute_confidence(fired, total, recommendation,
verifier_flagged)`.

Refinement (cap is dismiss-only): the flag-cap applies **only to a flagged dismiss**, not a flagged
escalate. The cap exists for one functional reason — to stop the Queue Agent auto-clearing a
*contested* benign call (ADR-0010); only a dismiss is ever auto-cleared, so only a dismiss needs
capping. Capping a flagged **escalate** served no routing purpose (an escalate never auto-clears — the
flag already routes it to `needsReview`) and actively *understated* a strong, contested catch: the hero
case fired 4/4 indicators yet displayed `REVIEW_THRESHOLD − 0.01`, reading as a weak, suspiciously
hardcoded number. A flagged escalate now keeps its true coverage confidence; the **verifier
disagreement**, not a depressed score, is what forces human review. This sharpens the demo beat —
"triage was fully confident on the pattern and the independent verifier *still* caught the benign
look-alike" — without changing any routing or measured metric.

Ordering (Phase 5): the orchestrator runs verify → confidence (passing `verifier_flagged`), and **never
overwrites the verifier's verdict**. Low confidence does not impersonate a verifier disagreement —
`verifier.status` always means "the verifier (dis)agreed" (the demo signal). "Needs human review" is a
**derived** condition computed downstream: `status == "flagged" OR confidence < REVIEW_THRESHOLD`.

Why: LLM self-reported confidence is poorly calibrated and indefensible under judging ("did the model
just make that number up?"). A coverage-based score is deterministic, explainable ("confidence = how
many of the typology's red flags this alert exhibits"), and agrees with the same indicators the
explanation cites.

Rejected: LLM self-reports a 0-1 float (uncalibrated). Fallback if this feels heavy: qualitative
High/Med/Low buckets, which are just bands of the same coverage score.
