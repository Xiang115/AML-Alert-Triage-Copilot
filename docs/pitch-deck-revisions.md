# Pitch-deck revisions — cited slide content

Paste-ready replacement content for `nexhack-aml-alert-triage-copilot-pitch.pptx`.
Every statistic carries a real `(Author, Year)` reference — never fabricate a citation.
**Rule:** any slide with a number gets a small source footer (see each block).

Sources used (verified 2026-06-22):
- PwC, *Towards Better Transaction Monitoring* (2019) — false-positive rate 90–95%.
- LexisNexis Risk Solutions, *True Cost of Financial Crime Compliance* — Global US$206.1bn (2023); **APAC US$45bn (2024)**.
- Jensen et al. (2023), *Nature Scientific Data* — SynthAML dataset.
- Industry operational estimates — alert first-pass review ~5–20 min/alert (range only; no single primary).

---

## SLIDE 3 — PROBLEM  *(rewrite: add the cited hook)*

**Section:** PROBLEM
**Title:** AML teams are drowning in false positives
**Subtitle:** The analyst still has to justify every call — even though ~9 in 10 alerts are benign.

**Three stat callouts (big):**
- **90–95%** of AML alerts are false positives  — *(PwC, 2019)*
- **US$45bn / yr** — APAC financial-crime compliance spend  — *(LexisNexis Risk Solutions, 2024)*
- **~5–20 min** of analyst time burned per alert, across the whole queue  — *industry estimate*

**Pain (keep):**
- Manual review repeats the same evidence-gathering work
- False positives consume analyst capacity
- Borderline calls need a second pair of eyes
- STR drafting is slow, inconsistent, and high-stakes

**Who (keep):**
- *User* — front-line AML analyst clearing a daily alert queue
- *Buyer* — Head of Compliance / MLRO who owns budget and regulatory risk
- *Core risk* — genuine suspicious flows get rushed

**Source footer:** `PwC (2019); LexisNexis Risk Solutions (2024).`

---

## SLIDE 9 — VALIDATION / METRICS  *(reframe: lead with workload, pre-empt the recall attack)*

**Section:** VALIDATION
**Title:** Honest metrics beat inflated metrics
**Subtitle:** On imbalanced AML data, accuracy alone misleads — a dismiss-all model scores 82.8% while catching zero launderers. So we lead with workload relief and the human safety net.

**Hero stat (lead with this):**
- **~68% less review time per alert** — modeled **14 min → 4.5 min** *(illustrative; review-time estimates span ~5–20 min/alert)*

**Measured (held-out SynthAML, n=250):**
- **81.74%** false-positive relief — of alerts the copilot dismisses, the share truly benign (safe to skip)
- **75.6%** accuracy vs labels — measured
- **82.8%** dismiss-all baseline — why accuracy alone is misleading

**Confusion matrix:** TP 1 · FP 19 · FN 42 · TN 188  (n=250)

> ⚠️ **NUMBERS-CONSISTENCY TODO (found 2026-06-25):** these n=250 figures **disagree with the served
> `metrics.json`** (n=60: 83.3% accuracy, 30% recall, baseline 83.3%). The live dashboard and this slide
> would show contradictory numbers under judging. **Resolve before recording:** run `python -m eval.evaluate
> --n 250` once on current code (fixed seed) and let that one authoritative run populate BOTH the slide and
> `metrics.json`. Until then, treat the slide numbers as provisional.

**Measured on SAML-D (real amounts + counterparties; Oztas et al., 2023, n=250) — we *did* the fix:**
- **68.8% accuracy vs 40.0% always-dismiss baseline** — on data that can express the patterns, the AI
  beats do-nothing by **+28.8 pts** (on SynthAML it merely *equalled* baseline).
- **72% recall** overall at **75% precision**, and the two detectors SynthAML couldn't even fire are now
  the strongest: **Fan-in (FI-01) 84%** · **Pass-through (PT-01) 77%** · **Structuring (ST-01) 74%**.
- **Coverage gap, quantified:** patterns outside the 5-card library (e.g. over-invoicing) score **25%** —
  honest proof the KB is a curated subset, not exhaustive.

**The honest line (now it names the fix, not just the gap):**
> SynthAML is amount-less and counterparty-less, so 3 of 5 detectors **can't even fire** — that number is
> a floor. So we re-measured on **SAML-D**, which carries the real signals: **fan-in and structuring jump
> from un-measurable to 68% / 63%**, and the copilot beats the dismiss-all baseline for the first time.
> Across both public sets we now measure **4 of 5 typologies**; KYC-mismatch is the one honest residual —
> it needs customer profile no public dataset carries.

**Caveat to state plainly:** the SAML-D slice is report-enriched for measurement power, so **recall and the
per-typology numbers are the honest, mix-independent figures** — lead with those, not the 68.8% accuracy.

**Presenter line:** Don't lead with accuracy. Lead with workload relief + the human-in-the-loop safety net — then own the floor honestly (data + coverage), don't spin it.

**Source footer:** `Measured on held-out SynthAML (Jensen et al., 2023), n=250, ADR-0004. Coverage: 2 of 5 typologies measurable (data + KB gaps). Time figures modeled/illustrative.`

---

## NEW / STRENGTHEN — goAML "real wire format"  *(promote from a slide-5 bullet to its own moment)*

**Section:** INTEGRATION SEAM
**Title:** Most AML tools stop at a draft. We emit the regulator's real filing.
**Subtitle:** On analyst sign-off, the approved STR exports as schema-valid goAML XML — the format Bank Negara Malaysia's FIU ingests.

- **Human-gated** — export unlocks only after an *escalate* sign-off; a change of mind to dismiss instantly revokes it.
- **XSD-validated** before it leaves — a malformed report can't be emitted.
- **Config-swap, not code** — point it at a specific FIU's registration in one file; demo schema → live schema.
- **Closes the loop** — filing returns a FIU submission reference (`MYFIU-2026-NNNNNN`).

*No external stat → no citation needed (product capability).*

---

## NEW — Deployment & data residency  *(add to Business Case, or its own slide)*

**Section:** DEPLOYMENT
**Title:** Built to run inside the bank's perimeter
**Subtitle:** The bank stays the reporting institution of record — and its data never leaves.

- **Your data never leaves your perimeter** — production runs on-prem / private VPC.
- **Provider-agnostic** — the LLM sits behind one swappable client; swap to a self-hosted open-weight model (Qwen / Llama / DeepSeek via vLLM/Ollama) as a **config change, not a code change**.
- **Nothing trained on customer data** — no labeled-data demand, no retraining, no drift monitoring, no model-risk governance, no black box a regulator can't interrogate.
- **Capital-light** — no GPU training farm, no in-house data-science org; an enterprise software team can run it economically on-prem.

*No external stat → no citation needed.*

---

## SLIDE 7 — ARCHITECTURE DIAGRAM  →  ⏳ LATER WORK (deferred per decision)

Do **not** redraw yet. Keep the current "codebase proof" list for now.
When picked up, the diagram must add what `docs/architecture.png` is missing:
`KB → Triage → Confidence → Verifier → STR Drafter → Human gate → goAML XSD validation → Audit trail`.
The rubric names "clear technical architecture **diagram**" as a full-mark item, so this is a real gap — just not now.

---

## NEW — VERIFIER SPOTLIGHT  *(the "wow" — give it its own slide; all values are real, from results.json)*

**Section:** THE WOW · ADVERSARIAL VERIFIER
**Title:** A second agent that challenges the first
**Subtitle:** This is what stops the copilot from being a confident-but-wrong autopilot.

**Case: HERO-001 · Aisyah binti Kamal · personal account AC-5001**

A 4-step flow across the slide:

1. **Trigger** — 5 inbound transfers from unrelated senders in 12 days, then forwarded onward. *Fan-in velocity rule fires.*
2. **Triage Agent** *(DeepSeek-v4-pro)* → **ESCALATE · 59% confidence** · matched **FI-01 Fan-in / Fan-out** *(FATF R.20; BNM)*. **3 of 4 indicators fired** — coverage shown as a checklist.
3. **Verifier Agent** *(DeepSeek-v4-flash)* → **🚩 FLAGGED — disagrees:**
   > "Outbound is partial (**RM2,000 of RM7,450**) to a company (*Ilmu Educational Supplies Sdn Bhd*) — not rapid full forwarding; consistent inbound amounts suggest a **legitimate merchant** receiving customer payments for supplies."
4. **Result** → routed to **human review**, *not* auto-escalated. A false positive caught; the analyst's time protected; accountability intact.

**Punch line:** *Triage matches the pattern. The verifier catches the benign look-alike.* An independent second line grounded on each typology's **distinguishing test** — not a redundant echo.

*No external stat → no citation (values are our own pipeline output).*

---

## NEW — ROADMAP HERO: MULE-NETWORK INVESTIGATION  *(the headline "what's next"; pays off live in the final round per ADR-0009)*

**Section:** ROADMAP · THE NEXT FRONTIER
**Title:** From one account to the whole network
**Subtitle:** Today the copilot reasons one alert at a time — exactly how an analyst (and a rule engine) sees the world, and exactly why network-distributed laundering slips through. Next: lift it from the account to the cluster.

**The shape (one diagram, centre of the slide):**

```
        originator ─┐
              mule ─┤
              mule ─┼──►  [ CONSOLIDATION ACCOUNT ]  ──►  beneficiary
       hidden mule ─┤            ▲
   benign account ──┘     Network Agent assigns each
   (cleared)             node a role + names the typology
```

**Why it's not just a link chart (the AI story):**
- **Structure you can trust** — a deterministic graph-walk links accounts by a *shared Consolidation Account*; **no hallucinated edges** — assembled from the data, not invented by the model.
- **Reasoning that earns "agentic"** — a precomputed **Network Agent** assigns each node a **role** (originator → mule → consolidation account → beneficiary), names the **network-scale typology**, and writes the narrative.

**The crafted cluster does two jobs at once:**
- **Finds** the **hidden mule** single-alert triage *correctly dismissed* — alone it looked benign; the network adds the cross-account evidence triage never had.
- **Clears** the **benign neighbour** that legitimately pays the same beneficiary — it discriminates, doesn't colour everyone red (the Verifier philosophy, extended to networks).

**The honest line (pre-empts the recall attack — pairs with Slide 9):**
> Account-level triage has a **recall ceiling only link-analysis breaks** — one account spreading laundering across a network is invisible until you see the network. Demo-data only; **changes no measured number** — a talking point, not a fabricated "network-improved recall."

**Demo placement:** a new **beat 3.5**, right after the Verifier — depth then breadth. The Verifier catches a wrong call on *one* alert; the network catches the hidden mule *across* alerts, then clears the benign one.

> **Use this as the visual for the Roadmap slide (11+12+13 block in the cut list).** In the 7-min video it's the headline roadmap tease ("we said this was next"); in the final round it's a live demo beat that pays it off.

*No external stat → no citation (roadmap capability + our own pipeline output).*

---

## 7-MINUTE VIDEO — CUT LIST  *(14→17 slides can't all be narrated; this is the budget)*

Target: **~3:15 pitch slides + ~3:30 live demo + ~0:15 close.** Roles:
**NARRATE** = spend time · **FLASH** = 2–3s visual transition · **PDF-ONLY** = keep in the README deck, skip in the video.

| Slide | Video role | Time | Why |
|---|---|---|---|
| 1 Title + hook | NARRATE | 0:20 | Name + one-line pitch |
| 3 Problem *(cited)* | **NARRATE** | 0:40 | The hook — 90–95% FP, APAC US$45bn. 20 marks. |
| 4 Solution loop | NARRATE | 0:25 | One-pass mental model |
| **Verifier spotlight** *(new)* | **NARRATE** | 0:25 | Tease the wow before the demo. Innovation = 30. |
| **goAML real-filing** *(new)* | NARRATE | 0:20 | "Most tools stop at a draft." Innovation = 30. |
| 9 Metrics *(honest)* | NARRATE | 0:30 | Workload relief + the recall pre-empt. |
| 11+12+13 Business / Pricing / Roadmap | NARRATE *(compressed to 1–2 slides)* | 0:35 | Market = 30. Headline only; detail in PDF. |
| **— LIVE DEMO —** | **SCREEN** | **3:30** | queue → open alert → triage + confidence checklist → **verifier catch (HERO-001)** → STR edit/approve → goAML export + filing receipt → audit trail |
| 10 Demo-flow bridge | FLASH | 0:05 | Cut straight into the screen recording |
| 14 Team + one-liner | NARRATE | 0:15 | Close |
| 2 Why-this-wins / rubric map | **PDF-ONLY** | — | Reads as gaming the rubric on camera; fine for judges reading the PDF |
| 5 Product features | **PDF-ONLY / FLASH** | — | Shown live in the demo anyway |
| 6 AI-pipeline detail | FLASH | 0:05 | Fold into the architecture beat |
| 7 Architecture | FLASH | 0:05 | Diagram is later-work; flash codebase-proof for now |
| 8 Dataset | FLASH | 0:05 | One line inside the metrics beat |
| Data-residency *(new)* | **PDF-ONLY** | — | Compliance buyers love it; no airtime in 7 min — save for final-round Q&A |

> Rule of thumb: anything the **live demo already shows**, don't also narrate as a slide.

---

## TEAM SLIDE — RESOLVED  *(2-person team; Nathaniel removed)*

**Section:** TEAM
- **Goh Kian Xiang** — *AI & Backend Engineer* — agent pipeline, FastAPI, precompute, eval, goAML export
- **Lee Zi Hao** — *Frontend Engineer* — React analyst console, demo integration & recording

**One-liner:** A two-person team — full-stack AI reasoning + a polished analyst console.

> Also fix the **README** team table to match (it still lists 3 with placeholder names *Marcus Tan / Priya Nair* and "team of three"). I can do that on request.

---

## PRODUCT NAME — options (pick one)

| Name | Angle | Note |
|---|---|---|
| **VerdictAML**  *(recommended)* | The product's value is a *defensible verdict* — triage proposes, verifier challenges, human signs. | Memorable, fintech-professional. Mild nuance: pair with "AI assists, analyst decides" so "verdict" doesn't read as autonomous. |
| **Crucible** | Every call is *tested* by the adversarial verifier. | Evocative of the wow; more abstract. |
| **ClearAML / Clarity** | Explainable, auditable — the regulator's ask. | Clean but more generic. |
| **AML Alert-Triage Copilot** | Pure descriptive — judges grok it instantly. | Safe fallback; use as the subtitle under whichever brand. |

**✅ LOCKED:** brand **VerdictAML** with subtitle *"AML Alert-Triage Copilot"* — memorable up top, instantly clear underneath. Replace **"AegisFlow" → "VerdictAML"** everywhere in the `.pptx` (slides 1 & 14 especially).
