# Metrics: measure accuracy for real, cite/model the time numbers

The metric slide (beat 5) and `GET /metrics` report four numbers. We decided to earn the ones we can
and transparently label the rest, rather than fabricate clean figures a judge could puncture:

- **accuracyVsLabels** — measured for real in `backend/eval/evaluate.py` over a **held-out** slice of
  SynthAML alerts (never seen during prompt tuning); % agreement of `recommendation` vs the
  Report/Dismiss label.
- **falsePositiveReduction** — measured, with an explicit definition stated on the slide: of the
  alerts the copilot recommends Dismiss, the share that are truly benign (label = Dismiss) — i.e. the
  benign review volume an analyst can safely skip. Stated precisely so it isn't read as a bigger claim.
- **avgReviewTimeBaselineMin** — a conservative midpoint (14 min) of published first-pass alert-review
  estimates (industry operational estimates put a Level-1 review at ~5–20 min/alert), labeled as a
  modeled assumption (we can't time real analysts in a hackathon). Presented as illustrative, never as
  a single measured/primary figure.
- **avgReviewTimeWithCopilotMin** — a conservative modeled estimate; time-saved is presented as
  illustrative, not measured.

This requires a held-out split fixed up front (tuning vs evaluation alerts) — otherwise accuracy just
measures memorization. Trade-off: less headline-grabbing than round fabricated numbers, but one real
held-out accuracy number plus honest labeling survives Q&A; fake precision does not.

**Sampling:** LLM-triaging all ~20k SynthAML alerts is too slow/costly under the deadline, so
`accuracyVsLabels` is measured over a **stratified random sample of the held-out slice (~100–300
alerts)** that preserves the ~17% reported ratio. It is still a real measured number; note the sample
size (n) on the metric slide so the claim is honest. Fix the random seed for reproducibility.

## Supporting external figures (deck Problem / Metric slides)

Every statistic shown on the pitch slides carries a real source — never a fabricated citation. Vetted
anchors (verified 2026-06-22):

- AML false-positive rate **90–95%** — PwC, *Towards Better Transaction Monitoring* (2019); corroborated
  by FCA and FinCEN-files data.
- Global financial-crime compliance cost **US$206.1bn (2023)** / **APAC US$45bn (2024)** — LexisNexis
  Risk Solutions, *True Cost of Financial Crime Compliance*.
- Alert first-pass review time **~5–20 min/alert** — industry operational estimates (a *range* only; the
  14-min baseline above is a modeled midpoint, not a single sourced figure).
- SynthAML dataset — Jensen et al. (2023), *Nature Scientific Data*.
