# Demo data is three explicit buckets

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
