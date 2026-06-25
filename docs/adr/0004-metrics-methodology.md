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

## Typology coverage — the held-out number measures 2 of 5 detectors (added 2026-06-25)

Re-measuring exposed that the held-out recall is **structurally capped**, and that the cap has
**two independent causes** which need different fixes. The metric now discloses this in-band
(`measuredTypologies` / `roadmapTypologies` / `coverageNote` on `GET /metrics`, computed by
`evaluate.coverage_fields()`), rather than leaving it as slide prose only:

- **Representation gap.** `synthaml_loader` reduces each alert to an aggregate feature row that is
  **amount-less and counterparty-less** (real SynthAML carries no currency amount, counterparty, or
  customer profile — ADR-0005). Only **PT-01** (pass-through) and **DA-01** (dormant-then-active) are
  expressible as timing/gap features (`medianCreditToDebitHours`, `postDormancyBurstFrac`). **FI-01**
  (needs distinct-counterparty counts), **ST-01** (needs cash amounts vs the RM25,000 CTR threshold),
  and **KYC-01** (needs declared profile) **cannot fire even when present**, so they are demonstrated on
  curated demo/hero data only and excluded from the measured number.
- **Coverage gap.** The KB is **5 curated FATF/BNM cards** (ADR-0002), deliberately not exhaustive. A
  real Report whose pattern matches **no** card is correctly `NO_MATCH`-dismissed by triage — and
  counted as a false negative. This is a hole in the typology library, not a triage error.

On Report/Dismiss-only SynthAML the two gaps **cannot be separated** (there is no per-alert typology
label), but both land **outside the 2 measurable detectors**, so the blended recall is an honest
**floor**, not the product ceiling. **Implication for the roadmap, stated plainly:** adding cards alone
will *not* move the SynthAML number (the data still can't express them) — the levers are **richer data
(SAML-D / IBM-AML)** to close representation *and* **a broader card library** to close coverage. Neither
is prompt tuning. The two-of-five disclosure is unit-tested (`test_evaluate.py`), including a partition
guard that fails if a future card is added without classifying its coverage.

**Update (2026-06-25): the data lever was acted on (ADR-0012).** Re-measuring on **SAML-D** (which
carries amount + counterparty) lifted **FI-01 to 68% and ST-01 to 63%** recall — from *structurally
unmeasurable* on SynthAML — and the copilot beat the always-dismiss baseline for the first time (61.6%
vs 40.0%, n=250, `saml_d_metrics.json`). The coverage gap was also quantified: typologies outside the
5-card KB scored 10% recall. Across both public sets, **4 of 5 cards are now measured**; KYC-01 is the
honest residual (no public set carries customer profile).

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
