# Confidence is computed from indicator coverage, not self-reported by the LLM

`TriageResult.confidence` (0-1) is computed, not asked of the model. The LLM does the grounded part it
is good at — deciding which of the matched typology card's indicators/dataSignals are actually present
in the evidence — and `confidence` is then derived as the fraction of the card's indicators that
fired, capped down when the Verifier flags. A `flagged` verifier can push confidence below the
human-review threshold.

Why: LLM self-reported confidence is poorly calibrated and indefensible under judging ("did the model
just make that number up?"). A coverage-based score is deterministic, explainable ("confidence = how
many of the typology's red flags this alert exhibits"), and agrees with the same indicators the
explanation cites.

Rejected: LLM self-reports a 0-1 float (uncalibrated). Fallback if this feels heavy: qualitative
High/Med/Low buckets, which are just bands of the same coverage score.
