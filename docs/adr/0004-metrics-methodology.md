# Metrics: measure accuracy for real, cite/model the time numbers

The metric slide (beat 5) and `GET /metrics` report four numbers. We decided to earn the ones we can
and transparently label the rest, rather than fabricate clean figures a judge could puncture:

- **accuracyVsLabels** — measured for real in `backend/eval/evaluate.py` over a **held-out** slice of
  SynthAML alerts (never seen during prompt tuning); % agreement of `recommendation` vs the
  Report/Dismiss label.
- **falsePositiveReduction** — measured, with an explicit definition stated on the slide: of the
  alerts the copilot recommends Dismiss, the share that are truly benign (label = Dismiss) — i.e. the
  benign review volume an analyst can safely skip. Stated precisely so it isn't read as a bigger claim.
- **avgReviewTimeBaselineMin** — a cited industry/published figure, labeled as an assumption (we can't
  time real analysts in a hackathon).
- **avgReviewTimeWithCopilotMin** — a conservative modeled estimate; time-saved is presented as
  illustrative, not measured.

This requires a held-out split fixed up front (tuning vs evaluation alerts) — otherwise accuracy just
measures memorization. Trade-off: less headline-grabbing than round fabricated numbers, but one real
held-out accuracy number plus honest labeling survives Q&A; fake precision does not.

**Sampling:** LLM-triaging all ~20k SynthAML alerts is too slow/costly under the deadline, so
`accuracyVsLabels` is measured over a **stratified random sample of the held-out slice (~100–300
alerts)** that preserves the ~17% reported ratio. It is still a real measured number; note the sample
size (n) on the metric slide so the claim is honest. Fix the random seed for reproducibility.
