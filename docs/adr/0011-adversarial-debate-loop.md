# A flagged Verifier opens a bounded adversarial debate that can flip the disposition — but a debated alert is never auto-cleared

The rubric is explicit that **depth beats breadth**: *"reward teams that solve one practical problem
deeply rather than teams that build many shallow features."* The recent additions (cost-sensitive
triage, reasoning timeline, Queue Agent) added *autonomy and surface*; this ADR adds **reasoning
depth** to the differentiator judges already remember — the adversarial Verifier — for the prelim
(deadline now 28 Jun). It is the chosen "deepen the existing pipeline" play over pulling the
Mule-Network feature (ADR-0009) forward, which stays a final-round build.

**Today the Verifier is a single pass.** Per ADR-0001 it re-reads the *raw* evidence (un-anchored,
never the Triage explanation) and emits `agreed | flagged`. That independence is the whole point — and
the trap a naive "debate" would spring: if Triage simply argues and the Verifier listens, we
re-introduce the anchoring ADR-0001 removed.

**Decision: on disagreement, escalate into a bounded one-round debate.** When — and *only* when — the
Verifier's first, independent pass **flags**, the two agents cross-examine: **Challenge → Rebuttal →
Re-verdict** (see `CONTEXT.md`). `agreed` cases never debate, so they are byte-identical to today and
carry zero regression risk; only the flagged minority runs the two extra turns. Independence is
preserved because the **Challenge is still the un-anchored first pass** — the debate is the resolution
*after* an independent disagreement, not a substitute for it. "Independent challenge first; structured
debate only on disagreement" is a principled extension of ADR-0001, not a reversal.

**The resolver is the Verifier re-judging itself — not a third agent.** After the **Rebuttal**, the
Verifier issues a **Re-verdict** with three outcomes: `holds` (flag stands → `needsReview`),
`convinced` (→ `agreed`), or Triage `conceded` (→ the **Disposition flips** `escalate↔dismiss`,
`agreed`). A separate adjudicator agent was rejected as more determinism surface and cost for no demo
gain.

**The debate may flip the disposition (the deepest cut).** A `flagged` escalate that Triage concedes
becomes a `dismiss` (and drops its `strDraft`); a `flagged` dismiss that Triage concedes becomes an
`escalate` (and drafts an STR in the debate path). A natural integrity guard falls out of the pipeline:
the debate only runs in the **matched-card branch**, so a `dismiss→escalate` flip is only possible when
a typology card *already matched* — the debate can never fabricate an escalation against no typology.

**Firewall: a contested alert is never auto-cleared.** Any alert that entered a debate routes to
`needsReview`; the **Auto-Clear Policy** (ADR-0010) clears only alerts the Verifier `agreed` with on its
*first, independent* pass. This is the safe cut: the disposition still flips and is shown + audited, but
the human-in-the-loop moat is untouched and `autoClearPrecision`/`autoClearedShare` (87% / 90%) are
**mathematically unchanged** by this feature — no risk to the headline slide 4 days out.

**Where the measured impact lands.** The debate's measured effect is on `accuracyVsLabels` / recall via
`dismiss→escalate` saves on the held-out slice (ADR-0004), not on the auto-clear numbers (firewalled).
Held-out evidence is aggregated and amount-less (ADR-0005), so expect *modest* held-out movement; the
debate **shines on the rich demo/hero cases** with clean transactions, exactly as the hero cases and the
Mule-Network roadmap already do. We report the re-measured held-out number honestly either way.

**Determinism (ADR-0003) holds.** Every turn runs at temperature 0 and is **precomputed** into
`results.json`; the timeline replays the recorded Challenge/Rebuttal/Re-verdict, so nothing flakes on
camera. The live `/triage` endpoint runs the full debate for Q&A.

**Demo placement.** Deepens beat 3 (the Verifier "wow"): the hero is now a **self-correction** — first-pass
Triage *dismisses* a crafted alert, the Verifier challenges it on the distinguishing test, and in the
rebuttal Triage recognises the pattern and **escalates** a real one the single pass missed → STR → goAML.
That turns the project's honest weakness (recall ceiling) into a watchable save. A second crafted case
keeps the original beat — Triage defends an escalate, the Verifier **holds** the flag → human review —
so both the `conceded` and `holds` outcomes are on screen.

**Consequences.** `agents/verifier.py` gains a `challenge()` (structured counter-hypothesis +
distinguishing-test assessment) and a `re_verdict()` (re-judge given the rebuttal); `agents/triage.py`
gains a `rebut()` turn; `agents/pipeline.py` runs the conditional debate and emits new
`challenge`/`rebuttal`/`reverdict` timeline events; `schemas.py` gains a `debate` object on
`TriageResult` (`challenge`, `rebuttal{argument, conceded}`, `reverdict{outcome, dispositionChanged,
note}`) and a `dispositionFlipped` flag; `queue_agent.py` firewalls debated alerts and writes a
`debateResolved` audit event; `confidence` recomputes from the post-debate recommendation + final
verifier status; the frontend timeline renders the back-and-forth. Regenerating `results.json` requires
the usual re-sync (hero-case check → fixture sync → re-eval), and `accuracyVsLabels`/recall are
re-measured; `autoClearPrecision` is asserted unchanged.

**Rejected.** (a) *Narrative-only debate* — shown but the final verdict stays the first pass: zero
regen risk but the rebuttal has no teeth, and Q&A spots it. (b) *Full cascade (debate-resolved alerts
auto-clear)* — bolder autonomy but reopens the recall risk and puts the 87% precision at stake 4 days
out; rejected in favour of the firewall. (c) *Third adjudicator agent* — more orchestration branding,
more cost and determinism surface. (d) *Pull Mule-Network (ADR-0009) into the prelim* — higher ceiling
but a 6-day build with a frontend long-pole; stays the final-round depth play.
