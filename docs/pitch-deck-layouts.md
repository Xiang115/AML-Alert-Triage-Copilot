# Pitch-deck layouts — design specs for the slides that change

Companion to `pitch-deck-revisions.md` (the *content* audit). This is the *layout* spec: drop-in
wireframes at the deck's real coordinates so the `.pptx` can be rebuilt without re-deriving the grid.
**No `.pptx` is edited here.** Covers only the slides the audit flagged: **11, 10, 4** (layout/content),
**2** (text only), and **slide-7 image** (composition).

## Design system (measured from the current deck — reuse as-is)

- **Canvas:** 13.33 in × 7.5 in (16:9, EMU 12192000 × 6858000). All coordinates below are **inches**.
- **Persistent chrome (keep on every slide, unchanged):**
  - Top hairline bar `(0,0)` 13.33 × 0.21, navy `#0E2841`.
  - Right rail panel `(11.67,0)` 1.67 × 7.5 navy `#0E2841` + teal stripe `#156082` at x≈11.98.
  - `AML / TRUSTED FINTECH` lockup at `(9.27,5.79)` (sits inside the right rail).
  - Slide number top-right `(12.19,0.40)` and bottom-right `(12.08,7.02)`.
  - Footer `NexHack 2026 · Track 2` `(0.75,7.02)` 3.75 × 0.25.
- **Content column:** x from **0.75** to **11.5** (right rail starts 11.67). Eyebrow/title/subtitle block:
  - Eyebrow `(0.75,0.44)` 6.88 × 0.29 — teal `#156082`, caps, letter-spaced.
  - Title `(0.75,0.85)` ~8.5 × 0.98 — navy `#0E2841`, bold.
  - Subtitle `(0.75,1.85)` ~8.96 × 0.65 — grey.
  - Source footer line `(0.75,6.73)` 10.0 × 0.19 — small grey.
- **Palette:** navy `#0E2841` (text/chrome) · teal `#156082` (accent/values) · orange `#E97132`
  (highlight / the "wow" / the honest gap) · green `#196B24` (positive) · light-blue `#0F9ED5` · grey `#E8E8E8`.
- **Stat-card pattern (from slide 11):** rounded rect 2.56 × 1.29, 0.06 accent bar on top edge; inside —
  value 0.48 tall (big), label 0.27, caption 0.23. Row of 4 at **x = 0.75 / 3.62 / 6.50 / 9.38**, y = 2.79
  (pitch 2.87, gap ≈ 0.31).

---

## SLIDE 11 — VALIDATION  *(biggest change: new numbers + add per-typology bars)*

Keep the 4-card top row (re-grid the same 4 slots, new values), and **replace the two bottom cards**
(confusion-only + SynthAML honest-line) with **per-typology bars (left)** and **honest-line + confusion
matrix (right)**. Lead-metric = recall; tint card 2 teal so the eye lands there.

```
┌ navy hairline ─────────────────────────────────────────────────────────────┐ ▌
  VALIDATION                                                             [11]  ▌rr
  Honest metrics, not inflated metrics                                         ▌  a
  Measured on REAL SAML-D — where fan-in & structuring can finally fire.       ▌  i
  ──────────                                                                   ▌  l
  ┌1: 0.75 ────┐ ┌2: 3.62 ────┐ ┌3: 6.50 ────┐ ┌4: 9.38 ────┐   y=2.79        ▌
  │▔green▔     │ │▔TEAL(lead)▔│ │▔teal▔      │ │▔grey▔      │   2.56×1.29     ▌
  │ ~68% less  │ │   72%      │ │  68.8%     │ │  60.4%     │                  ▌
  │ Review time│ │ Catch-rate │ │ Accuracy   │ │ Auto-clear │                  ▌
  │ 14→4.5 min │ │ (recall)   │ │ vs labels  │ │ precision  │                  ▌
  │            │ │ @75% prec. │ │ +28.8 pts  │ │ 42.4% auto │                  ▌
  └────────────┘ └────────────┘ └────────────┘ └────────────┘                 ▌
  ┌ Per-typology recall (0.75,4.44) 5.35×1.95 ┐ ┌ The honest line (6.69,4.44) 5.35×1.95 ┐
  │ FI-01  Fan-in        ███████████░ 84% 48/57│ │ Real SAML-D carries amount + counterparty,│
  │ PT-01  Pass-through  ██████████░░ 77% 27/35│ │ so fan-in & structuring are measurable for│
  │ ST-01  Structuring   █████████░░░ 74% 28/38│ │ the first time — the strongest detectors. │
  │ Gap    off-KB        ███░░░░░░░░░ 25% 5/20 │ │ 4 of 5 FATF/BNM cards measured; KYC-01 the│
  │ (orange = honest coverage gap)            │ │ honest residual. Lead with recall.        │
  │                                           │ │ ── Confusion (n=250): TP108·FP36·FN42·TN64│
  └───────────────────────────────────────────┘ └───────────────────────────────────────────┘
  Source: Measured on held-out SAML-D (Oztas et al., 2023), n=250, ADR-0012. 4 of 5 typologies measured. Time figures modeled.
  NexHack 2026 · Track 2                                                  [11]  ▌
```

**Shape-by-shape change table** (existing shape names from `slide11.xml`):

| Shape | Action | New content / note |
|---|---|---|
| Rect 41 (subtitle) | edit | "Measured on **real SAML-D** — where fan-in & structuring can finally fire. On imbalanced data, recall beats accuracy." |
| Card 1 (Rects 46/47/48) | keep | `~68% less` / `Review time per alert` / `14 → 4.5 min`. Accent bar → green `#196B24`. |
| Card 2 (Rects 51/52/53) | **edit + emphasise** | `72%` / `Catch-rate (recall)` / `@ 75% precision`. **This is the lead** — accent bar + value teal `#156082`; optional faint teal fill so it reads as hero. |
| Card 3 (Rects 56/57/58) | edit | `68.8%` / `Accuracy vs labels` / `+28.8 pts vs 40% baseline`. |
| Card 4 (Rects 61/62/63) | edit + de-emphasise | `60.4%` / `Auto-clear precision` / `42.4% of queue auto-cleared`. Accent bar grey `#E8E8E8` (depressed by enriched slice — don't let it read as the headline). |
| Card "Confusion" (RRect 64, Rects 65/66) | **repurpose → Per-typology bars** | Re-title `Per-typology recall (measured)`; grow to `(0.75,4.44)` 5.35 × 1.95. Add 4 horizontal bars (see below). |
| Card "Honest line" (RRect 67, Rects 68/69) | edit + move | Re-pos to `(6.69,4.44)` 5.35 × 1.95. New honest-line text (SAML-D coverage). **Append** confusion matrix as a divided sub-line: `Confusion (n=250): TP 108 · FP 36 · FN 42 · TN 64`. |
| Rect 70 (source) | edit | `Source: Measured on held-out SAML-D (Oztas et al., 2023), n=250, ADR-0012. Coverage: 4 of 5 typologies measured. Time figures modeled/illustrative.` |

**Per-typology bar geometry** (inside the left card; track = light grey `#E8E8E8`, fill = teal, gap-bar = orange):

| Bar | Label x=1.04 | Track x=3.10 → 5.65 (2.55 wide = 100%) | Fill | % text x=5.75 | n x=6.10 |
|---|---|---|---|---|---|
| FI-01 Fan-in | y≈4.86 | fill 84% → 2.14 wide | teal | `84%` | `48/57` |
| PT-01 Pass-through | y≈5.18 | 77% → 1.96 | teal | `77%` | `27/35` |
| ST-01 Structuring | y≈5.50 | 74% → 1.89 | teal | `74%` | `28/38` |
| Gap (off-KB) | y≈5.82 | 25% → 0.64 | **orange `#E97132`** | `25%` | `5/20` |

> Bars are the strongest, now-true story — they're what the SynthAML version literally *could not show*.
> The orange coverage-gap bar is deliberate honesty, not a flaw to hide.

---

## SLIDE 10 — DATASET  *(reframe SynthAML-only → SAML-D primary + SynthAML, per ADR-0012)*

Same two-column card skeleton already on the slide (left card x≈1.04, right card x≈7.02, "how we use it"
band at bottom). **Swap the meaning of the columns**: left = SAML-D (the measurement + demo set), right =
SynthAML (timing + scale). Bottom band carries the honest-use + KYC-01 residual line.

```
  DATASET                                                                [10]  ▌rr
  Two public datasets — each used for what it can prove                        ▌  a
  Real amounts + counterparties drive the metric; SynthAML adds timing + scale.▌  i
  ┌ LEFT card (1.04,3.04) 4.27 wide ───────────┐ ┌ RIGHT card (7.02,3.04) ───────────┐
  │ ▔teal▔  SAML-D · Oztas et al., 2023        │ │ ▔grey▔  SynthAML · Jensen et al., 2023 │
  │  Measurement + demo set (held-out n=250)   │ │  Scale + timing reference              │
  │  • Real amount + counterparty + channel    │ │  • 20,000 alerts / 16M+ transactions   │
  │  • FI-01 / ST-01 / PT-01 can finally fire  │ │  • Powers DA-01 (dormant-then-active)  │
  │  • £/€ flows = the live demo queue (SD-…)  │ │  • Amount-less, no counterparty (limit)│
  └────────────────────────────────────────────┘ └────────────────────────────────────────┘
  ┌ How we use it honestly (full-width band, y≈5.83) ───────────────────────────────────────┐
  │ 4 of 5 FATF/BNM cards measured across both sets; KYC-01 is the one residual no public set │
  │ carries. Hero cases (HERO-001/002/003) are crafted on top — separate, never counted in metrics. │
  └──────────────────────────────────────────────────────────────────────────────────────────┘
  Source: Oztas et al. (2023), SAML-D · Jensen et al. (2023), Nature Scientific Data / SynthAML.
```

| Shape | Action | New content |
|---|---|---|
| Title (sp `What the 935MB SynthAML data is`) | edit | `Two public datasets — each used for what it can prove` |
| Subtitle | edit | `Real amounts + counterparties drive the metric; SynthAML adds timing + scale.` |
| Left-card header `SynthAML, Jensen et al. 2023` | edit | `SAML-D · Oztas et al., 2023` (accent teal). |
| Left-card 4 bullets | edit | "Measurement + demo set (n=250)" / "Real amount + counterparty + channel" / "FI-01·ST-01·PT-01 can fire" / "£/€ flows = the live demo queue". |
| Right-card header `Important limitation` | edit | `SynthAML · Jensen et al., 2023` (accent grey — secondary). |
| Right-card 4 bullets | edit | "Scale + timing reference" / "20k alerts / 16M+ txns" / "Powers DA-01 (dormant-then-active)" / "Amount-less, no counterparty *(limitation)*". |
| `How we use it honestly` band | edit | 4-of-5 measured + KYC-01 residual + hero-cases-separate line (above). |
| Source footer | edit | add **Oztas et al. (2023), SAML-D** before the SynthAML cite. |

---

## SLIDE 4 — VERIFIER SPOTLIGHT  *(content edit inside the existing 3-column flow; +optional cap visual)*

Layout stays: left column = HERO-001 identity + Trigger (x1.02), middle = Triage Agent (x4.62), right =
Verifier Agent (x8.62), Punch-line band at bottom. **Only the Triage card body changes** + an optional
confidence-cap micro-bar that *visualises* ADR-0007 (the wow mechanic).

```
  Triage Agent (4.62,3.00)                Verifier Agent (8.62,3.00)
  ESCALATE · 100% confidence              🚩 FLAGGED — disagrees
  Matched FI-01 Fan-in / Fan-out          Retention of funds, partial forwarding
  ▸ 4 of 4 indicators fired               to a business counterparty, consistent
  ▸ full pattern match — yet the          inbound amounts → legitimate merchant,
    independent verifier disagrees        not mule consolidation.
    → human review                        (grounded on FI-01's distinguishing test)
  ┌ coverage bar (4.62,4.78) 2.81×0.18 ───┐
  │ coverage 4/4 ████████████████████ 100%│   full teal fill — the verifier's flag, not a
  └────────────────────────────────────────┘   low score, is what routes it to review
```

| Shape | Action | New content |
|---|---|---|
| Triage body (sp `Matched FI-01 … 3 of 4 indicators…`) | **edit** | `Matched FI-01 Fan-in / Fan-out.` newline `4 of 4 indicators fired → 100% pattern confidence — yet the independent verifier disagrees (benign merchant) → human review.` |
| `ESCALATE · 59% confidence` | **edit** | `ESCALATE · 100% confidence` (4/4 indicators; no longer capped — ADR-0007 caps only a flagged dismiss). |
| Verifier body | keep / light edit | already accurate; can tighten to the merchant paraphrase above. |
| **NEW** coverage micro-bar | add (optional) | `(4.62,4.78)` 2.81 × 0.18. Full teal fill (4/4 = 100%), light-grey remainder = none. Caption: "full pattern match — the verifier's disagreement, not a low score, forces human review." |

> Why this is *better*, not just corrected: the old "3 of 4 / 59%" implied the AI was unsure. The truth is
> stronger — **triage was 100% confident on the pattern, and the independent verifier still caught the
> benign look-alike**; the disagreement alone forces human review (ADR-0007).

---

## SLIDE 2 — PROBLEM  *(text only, no layout change)*

3rd stat card caption currently `Flagright, 2026`. **Verify that source actually states ~5–15 min/alert.**
If unconfirmed, revert caption to `industry estimate` and drop `Flagright (2026)` from the source footer
(repo rule: never ship an unverifiable citation). No geometry change either way.

---

## SLIDE 7 — COCKPIT IMAGE  *(composition spec for the replacement screenshot — do NOT generate yet)*

Current: full-bleed `(0.00,0.00)` 13.33 × 7.5 image = two stale hand-built mockups. Replace with **one
real screenshot of the running frontend**, exported at **2560 × 1440 (16:9)** to fill the frame edge-to-edge
(or inset to slide-9's safe frame `(0.56,0.19)` 12.21 × 7.12 if a navy border is wanted).

**Must be visible in the capture (open HERO-001 to keep the verifier-catch narrative):**
1. **Left queue** — real holders only: `SD-000x` ("SAML-D account …") + `HERO-001 Aisyah binti Kamal`
   tagged FLAGGED. No invented names (no "Daniel Foong / Suriana Mart").
2. **Indicator coverage = 4 of 4 fired** (matches results.json — not the old "3 of 4").
3. **ESCALATE · 100%** with the verifier **🚩 flagged / human-review** panel.
4. **STR draft** panel on the right (shows the goAML-ready output).

> Decide hero vs real-data framing: HERO-001 (RM, named subject) reads cleanest for the wow; a SAML-D case
> (£/€) better matches slide 10/11. Ideal: capture **both** and let slide 7 show the hero, with a SAML-D
> shot held for Q&A. Two near-identical mockups on one slide is redundant — one accurate frame is enough.

*Slide 9 architecture image — **does** need a targeted redraw; see the section below.*

---

## SLIDE 9 — ARCHITECTURE DIAGRAM  *(targeted redraw — keep the skeleton, fix 4 boxes)*

Verified against `agents/pipeline.py`, `store.py`, `main.py` on 2026-06-26. The 4-column skeleton
(BANK/ANALYST · FASTAPI BACKEND · AI PIPELINE · REGULATOR SEAM) and the **whole REGULATOR SEAM are
correct — keep them.** The diagram predates two big additions: the **adversarial debate + concession
gate** and the **SQL persistence layer**. Edit these boxes:

### AI PIPELINE column — the main gap (replace the 5-step list with the real flow)

The current `1 Evidence → 2 KB → 3 Triage → 4 Confidence → 5 Verifier+STR` is a single line. The real
pipeline branches on a flag and runs a debate. Redraw as:

```
 Typed Agent Pipeline  (agents/pipeline.py → TriageResult, streamed as SSE events)
 1 Evidence Renderer        AlertInput → raw evidence text
 2 Typology KB + retrieve   rank/select FATF·BNM cards  (data/typologies/)
 3 Triage Agent             DeepSeek-v4-pro · cost-sensitive · indicators only
 4 Citation Grounding       clamp cited txn IDs to the real ledger (can't cite a ghost)
 5 Verifier                 DeepSeek-v4-flash · distinguishing test / benign look-alike
 ├─[only if FLAGGED]──────────────────────────────────────────────┐
 6 Adversarial Debate       Challenge → Rebuttal → Concession Gate │  ← NEW (ADR-0011/0012)
   • cost-sensitive gate: dismiss→escalate always honoured;        │     the headline
     strong multi-indicator escalate HOLDS for a human (not dropped)│     recent work
   • else Re-verdict (holds / convinced / conceded)               │
 └──────────────────────────────────────────────────────────────┘
 7 Confidence               from coverage, CAPPED below review threshold on a flag (ADR-0007)
 8 STR Drafter              structured STR — escalate only
 ▸ Swappable LLM Client     hosted DeepSeek now; self-hosted later  (keep as-is)
```

- **Must-add box: "Adversarial Debate + concession gate"** with a small *loop/branch arrow off the
  Verifier* labelled "only on a flag." This is the wow and it's currently invisible.
- Split "5 Verifier + STR Draft" into **separate Verifier and STR Drafter** boxes (they're separate agents).
- Add the **Citation Grounding** box between Triage and Verifier.
- Edit Confidence caption → "…computed from indicator coverage; the verifier's disagreement forces human review (a flagged dismiss is also capped below the threshold)."

### FASTAPI BACKEND column

- **Rename "In-Memory Store" → "SQL Store (SQLAlchemy)".** Caption: `SQLite (demo) → Postgres/MySQL via
  DATABASE_URL, no code change`. List the **4 tables: alerts · transactions · decisions · audit**.
  `results.json / metrics.json` are the seed/catalog, but decisions + audit are **durable**.
- **Update "API Routes"** to the real surface (paths are nested; several are missing):
  `GET /alerts` · `GET /alerts/{id}` · `POST /alerts/{id}/triage` · **`GET /alerts/{id}/triage/stream` (SSE
  live reasoning)** · `POST /alerts/{id}/decision` · `GET /alerts/{id}/str.xml` · `POST /alerts/{id}/str/submit`
  · **`GET /queue/briefing`** · `GET /audit` · **`GET /audit/summary`** · `GET /metrics` · `GET /health` · `POST /reset`.
- **Audit Trail box** — note it now records **debate-resolution + auto-clear seed events** too (not just
  decision/submission), and it's a durable SQL table.

### BANK / ANALYST column (minor)

- React console bullets: add **"live reasoning stream (SSE 'thinking' view)"** alongside the Q&A button.
- Optional new small node: **Queue Agent** (`queue_agent.py` auto-clear → `GET /queue/briefing`) — the
  thing that pre-triages/auto-clears the queue. Place near the console or as a backend node.

### No change needed

- **REGULATOR SEAM** (goAML Serializer → XSD validates → BNM FIU `MYFIU-2026-NNNNNN` → Case Management roadmap) ✅
- Legend (solid = implemented, dashed = roadmap) ✅. Optionally add a one-line note that the served data is **SAML-D (ADR-0012)**.

> Scope: this is ~4 edited boxes + 1 new debate box + 1 split, not a fresh diagram. The tool that made
> `image1.png` (looks like a draw.io / Excalidraw / Figma export) should reopen the source and patch the
> AI-PIPELINE + STORE + ROUTES boxes.
