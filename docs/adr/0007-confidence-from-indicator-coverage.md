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

Why: LLM self-reported confidence is poorly calibrated and indefensible under judging ("did the model
just make that number up?"). A coverage-based score is deterministic, explainable ("confidence = how
many of the typology's red flags this alert exhibits"), and agrees with the same indicators the
explanation cites.

Rejected: LLM self-reports a 0-1 float (uncalibrated). Fallback if this feels heavy: qualitative
High/Med/Low buckets, which are just bands of the same coverage score.
