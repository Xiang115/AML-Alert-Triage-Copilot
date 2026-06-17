# Demo data is three explicit buckets

The dataset is **SynthAML** (Jensen et al. 2023, *Nature Scientific Data*; Spar Nord), downloaded from
Figshare DOI `10.6084/m9.figshare.c.6504421.v1` — not a Kaggle "synthetic AML" notebook. ~20k alerts +
~16M transactions with reported/dismissed outcomes, one alert → many transactions.

To reconcile the engineered hero case (ADR-0003) with the real held-out accuracy number (ADR-0004),
we split the data into three buckets and keep them clearly separate:

1. **Demo queue (~10-15 alerts)** — real SynthAML rows hand-picked to look like an analyst's morning
   (mostly false positives, a few real), each mapping to one typology card. On screen for beats 1-4;
   precomputed into `results.json`.
2. **Hero cases (2-3, hand-crafted)** — the verifier-catch case plus 1-2 benign look-alikes
   (high-turnover business, salary/rent). Synthetic, used only for the narrative, **never counted in
   accuracy**.
3. **Held-out eval slice (large, untouched)** — a separate SynthAML split never seen during prompt
   tuning; `backend/eval/evaluate.py` measures `accuracyVsLabels` over it. **Never shown in the demo.**

The held-out split must be carved **before** any prompt tuning (Person B's first data task) or the
accuracy number just measures memorization. Q&A honesty line: "accuracy is measured on held-out real
SynthAML alerts; the on-screen hero case is a crafted illustration of the verifier mechanism."

Rejected: all-raw-SynthAML (can't guarantee the on-camera verifier catch) and all-hand-crafted
(accuracy becomes self-graded fixtures, meaningless).

## Typology vs data reality (drives which bucket each typology lives in)

SynthAML transactions carry only `timestamp`, `entry type`, `transaction type`, `transaction size`
(no counterparty identity, no account holder/KYC profile, no running balance). So not every encoded
typology can be evidenced from real rows — that decides demo-queue vs hero-case placement:

| Typology | Real SynthAML rows? | Placement |
|---|---|---|
| Pass-through / rapid movement | yes (in/out + computed runningBalance) | demo queue |
| Dormant-then-active | yes (timestamp gap + size jump) | demo queue |
| Structuring | partial (size clustering near RM25k; "cash" only if `transaction type` encodes it) | demo queue |
| Fan-in / fan-out | no (needs counterparty identity SynthAML lacks) | **hero case (hand-crafted)** |
| KYC profile mismatch | no (needs customer profile SynthAML lacks) | **hero case (hand-crafted)** |

`runningBalance` is computed (per-account cumulative sum); `direction` derived from `entry type`;
`Account` holder/type/KYC fields are synthesized per alert for display. Card `dataSignals` for the
demo-queue typologies must reference only fields that exist or are derivable on real rows; counterparty-
and profile-dependent signals belong to the hero cases. Confirm actual CSV headers/categories on
download before finalizing the loader.

## Update — Phase 1, after profiling the real data (supersedes the table above)

The real columns are `AlertID, Date, Outcome` (alerts) and `AlertID, Timestamp, Entry(Credit|Debit),
Type(Card|Wire|Cash|International), Size` (transactions), with **median ~829 transactions per alert**
and **`Size` a normalized float (mean 0, std 1, ~half negative) — NOT a currency amount**. There is no
counterparty, no holder, no KYC, and no usable money value. Consequences:

- **No clean on-screen vignette is possible from real rows** — they are dense, amount-less, counterparty-
  less histories. Even pass-through/dormant can't be shown as a tidy 2–3 transaction story, and
  structuring (a threshold pattern) is impossible without real amounts.
- **Decision (grill, Phase 1): real SynthAML powers the held-out accuracy metric ONLY; the entire
  on-screen demo queue AND the hero cases are hand-crafted.** The earlier "demo queue = real rows"
  premise is dropped.
- Triage cannot read ~829 raw rows, so the loader (`backend/synthaml_loader.py`) reduces each alert to
  a fixed **`AlertFeatures`** record (volume, credit/debit, channel mix incl. cash/international,
  span/dormancy/burst, size distribution, net flow), precomputed once to **`backend/data/alert_features.csv`**
  (committed, ~20k rows). The frozen 80/20 stratified split lives in **`backend/data/holdout_alert_ids.json`**
  (committed; 16,000 held-out, 0.172 Report ratio preserved in both sets).
- The hand-crafted demo/hero cases keep full fields (counterparty, MYR amounts, runningBalance) and carry
  all narrative typologies; they are never counted in accuracy.
