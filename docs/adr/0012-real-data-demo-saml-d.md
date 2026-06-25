# ADR-0012 — Real-data demo + measurement on SAML-D (retire the hand-written demo bucket)

**Status:** Accepted (2026-06-25). Amends ADR-0005 (three-bucket data) and ADR-0004 (metrics).

## Context

Re-measurement (see ADR-0004 addendum) exposed that our story rested on two different data
universes that never met: the **demo** ran on hand-authored alerts (curated `demo_queue.json` +
crafted `hero_cases.json`), while the **measured** number ran on SynthAML feature-aggregates that
are amount-less and counterparty-less — so 3 of 5 typologies could not fire, and a judge could
fairly say "it only works on cases you wrote." Two gaps cap the SynthAML number: a **representation
gap** (the dataset omits counterparty/amount/profile) and a **coverage gap** (the 5-card KB is not
exhaustive). Neither is fixed by prompt tuning; both are fixed by **better data**.

## Decision

Drive both the on-screen demo **and** the measurement off **real, public, typology-labelled data**,
mixing two complementary synthetic sets, and retire the hand-written demo bucket:

- **SAML-D** (Oztas et al., 2023) — rows carry **amount + counterparty + per-transaction
  `Laundering_type`**. `data/saml_d_loader.py` builds **real account-centric Alerts** (an Alert =
  one account's windowed inbound+outbound ledger) the *same* pipeline reasons over via the rich
  `render_alert_evidence` path. Produces a real **demo queue** (`saml_d_demo_queue.json`) and a
  labelled **held-out slice** (`saml_d_holdout.json`), pools disjoint (no demo case is measured).
- **SynthAML** remains the held-out source for **DA-01** (dormant-then-active), which SAML-D has no
  analogue for. Together the two sets measure **4 of 5 cards** (PT-01, FI-01, ST-01 on SAML-D; DA-01
  on SynthAML). **KYC-01** stays an honest residual — no public set carries customer profile.
- **Hand-written cases are removed from the served queue**; `hero_cases.json` is kept **only as a
  labelled fallback** for Beat 3 if no clean real verifier-catch is mined (per the team decision).

### Modeling choices (deliberate, so they are inspectable, not hidden)

- **Alert = account-centric windowed ledger.** Typology patterns are only visible account-centrically
  (fan-in needs the *receiver's* many inbound legs; structuring needs the depositing account's many
  sub-threshold legs). Direction is inbound when the alert's account is the receiver. Window capped
  (~12 legs) and centred on the laundering cluster for readability.
- **`runningBalance` is synthesised** from the cumulative signed flow over the window (SAML-D has no
  balance) — a reconstruction from *real* flows, surfaced as derived. It lets the "drains to ~0" mule
  tell appear without inventing a transaction.
- **Account profile is unknown** (`accountType: "unknown"`, placeholder holder/openedAt). We do **not**
  invent a customer — which is exactly why KYC-01 cannot be scored here.
- **No label leakage:** `Is_laundering` / `Laundering_type` never enter the evidence; transaction
  `flags` are rule-derived (`cross-border`, `cash`) only. The label is used solely to *score*.
- **Typology mapping** (`TYPOLOGY_MAP`): only clear matches map; ambiguous patterns map to **None**
  and form the **coverage gap, now a real number** — e.g. `Over-Invoicing`, `Cash_Withdrawal`,
  `Behavioural_Change_*` (~21% of SAML-D laundering txns) are real laundering our KB does not describe.

## Consequences

- The demo can no longer be dismissed as "crafted cases" — it runs on published AML data, end to end.
- FI-01 and ST-01 — invisible on SynthAML — are **measured for real** (per-typology recall in
  `saml_d_metrics.json`). The coverage gap is quantified instead of argued.
- Cost: a one-time `saml_d_loader.build` over the 1 GB CSV; a precompute over the real demo queue; a
  held-out eval run. Realism trade-offs: numeric counterparty ids (no names) and a synthesised running
  balance — both flagged, both honest.
- The "demo determinism" guarantee (ADR-0003) is unchanged: results are still precomputed at temp 0.

## Measured outcome

**Real-data demo (precomputed, 22 SAML-D alerts + 3 HERO fallback, cost-sensitive).**
Pipeline vs ground truth on the demo set: PT-01 **4/4** caught, FI-01 **2/4**, ST-01 **1/4**;
benign look-alikes **3/4** correctly dismissed, normal **5/6** dismissed. Small/illustrative —
the held-out slice is the real metric — but already shows pass-through reads cleanly while
fan-in/structuring are hard from transactions alone.

**Verifier "wow" — mined from real data, no longer hand-engineered.** `SD-00013`: a real
benign account that triage escalated as FI-01; the Verifier challenged it ("legitimate merchant —
no rapid full forwarding, repeat customers, not a personal account"); Triage **conceded → dismiss.
Correct.** This is the Beat-3 differentiator on *real* data. `HERO-001` is retained only as a
labelled fallback.

**Key honest finding — the adversarial debate (ADR-0011) trades recall for precision on real data.**
The *same* benign-merchant challenge that correctly clears SD-00013 also flipped **true** FI/ST
reports to dismiss (SD-00005, SD-00009/10/11), because "retained balance / no full forwarding" is
**not discriminative** on SAML-D — real consolidation accounts also retain a balance. So the debate
lowers matched-card recall. This was invisible while everything was hand-crafted; it is now measured,
not hidden. Lever: a more discriminative distinguishing test, or gate the debate so it cannot concede
away a strong multi-indicator match.

**Determinism caveat (amends ADR-0003).** DeepSeek V4 is not bit-deterministic even at temperature 0
(SD-00002 flipped dismiss↔escalate between two runs). The precomputed `results.json` and the mined
wow must therefore be **locked once recorded** — do not regenerate the demo artifacts before filming.

**Held-out per-typology recall (SAML-D, n=250 — `saml_d_metrics.json`).** The payoff of the whole
exercise: on data that *can* express the typologies, the copilot **beats baseline for real**, and the
two detectors SynthAML could never measure now work.

- **accuracyVsLabels 61.6% vs baseline (always-dismiss) 40.0%** — +21.6 pts. (On SynthAML accuracy
  *equalled* baseline; the AI added nothing. Here it clearly does.)
- **recall 55.3%** (83/150) — vs ~30% on SynthAML. **precision 74.1%.** confusion tp83/fp29/fn67/tn71.
- **Per-typology recall — the headline:** **FI-01 68.4% (39/57)**, **ST-01 63.2% (24/38)**, **PT-01
  51.4% (18/35)**. Fan-in and structuring were *0-of-5 measurable* on SynthAML; they are now measured
  and the strongest detectors.
- **Coverage gap, quantified:** the uncovered typologies (Over-Invoicing etc.) score **recall 10%
  (2/20)** — empirical confirmation that patterns outside the 5-card KB are (correctly) not caught.

**Honesty caveats on these numbers.** (1) The slice is **report-enriched** (150 report / 100 normal)
for measurement power, so *accuracy/precision reflect that ~60% positive mix, not the real ~0.1%
base rate* — **recall and per-typology recall are the mix-independent truths**; lead with those.
(2) This run is **triage + verifier without the debate**; the demo precompute showed the debate
(ADR-0011) further *reduces* FI/ST recall, so the production-with-debate recall is lower than 55%.

**Combined coverage across both real datasets: 4 of 5 cards measured** — PT-01/DA-01 on SynthAML,
PT-01/FI-01/ST-01 on SAML-D. **KYC-01 remains the honest residual** (needs customer profile no public
set carries).
