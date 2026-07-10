# NexHack 2026 Post-Mortem — Why VerdictAML Placed 9th

An evidence-based comparison of VerdictAML against the three winning repos:
champion [ComplianceGuard](https://github.com/sonnysanputra/ComplianceGuard),
2nd place [CukaiPandai](https://github.com/chaosiris/CukaiPandai),
3rd place [CompliMY](https://github.com/j4ryl/CompliMY).

## TL;DR

We did not lose on engineering. Our codebase (~31k lines of Python/TS, 37 test files,
goAML XSD-validated export, measured held-out metrics) is deeper and more
production-credible than the champion's (~10.5k lines). We lost on **the demo and the
pitch** — and to a champion who built *the same product* and out-demoed us on every
axis a judge can see in 7 minutes.

## Finding 1 — The champion built our product, head-to-head

ComplianceGuard is an AML alert-triage copilot: auto-clears false positives with an
audit trail, learns suppression patterns from analyst clearances, drafts a
regulator-style SAR, human gate on every filing. Feature-for-feature our pitch.
Judges could compare us directly, and on the visible axes they won:

| Axis | ComplianceGuard (1st) | VerdictAML (9th) |
| --- | --- | --- |
| Demo runtime | 14 agents run **live**, streamed to the UI via SSE — judges watch the AI work | Pipeline **precomputed offline**, served from memory; public Render instance runs **keyless**, so the LLM never fires during judging |
| Input | Upload **any** PDF/DOCX/CSV or a **scanned Maybank statement (OCR)** → 14/14 transactions extracted live | Bundled SAML-D fixtures, curated hero cases pinned to the top of the queue |
| Privacy story | **Local LLM (Qwen/Ollama) demonstrated** — "data never leaves the bank" | Hosted DeepSeek now, "self-host is a config change" later — same argument, but promised instead of shown |
| Investigation breadth | 7 parallel evidence agents: watchlist, adverse media (live web), KYC checks, policy RAG with citations, money-flow graph | Triage → verifier → STR draft (deeper governance, narrower investigation) |

The lesson is brutal but simple: in an agentic-AI hackathon, **showing the agents
run is the product**. A precomputed replay — however honest the architecture reasons
(latency, determinism, keyless resilience) — reads as a mock UI next to a live stream.

## Finding 2 — Our differentiation doesn't demo

Our genuinely superior material — the leakage/coverage frontier, computed indicator
confidence, append-only audit trail with mandatory override reasons, schema-valid
goAML export — is governance depth. It is the most regulator-real work of all four
repos, and it is **invisible on stage**. "Watch it OCR a scanned bank statement"
beats "0 observed leaks, 3.75% upper bound" in every 7-minute room.

We also published honest measured metrics (recall 0.69, precision 0.73, accuracy
0.66). The champion published **no measured accuracy at all** — every number
labeled *(industry estimate)* or *(illustrative)*. To a non-expert judge, our
honesty reads as "misses a third of the laundering"; their storytelling reads as
vision. Next time: lead with the workload number (43% of the queue auto-cleared,
zero leaks), never with model accuracy.

## Finding 3 — The pitch was the biggest controllable loss

- Our finals delivery was a pre-recorded video with poor audio and a presenter
  reading a script. In judged finals, delivery routinely swings a third or more of
  the score.
- The winners treated the pitch as a first-class engineering deliverable:
  - ComplianceGuard ships a 360-line `PRESENTATION.md`: per-slide speaker notes,
    rehearsed soundbites ("Copilot, not autopilot", "Rules decide, AI explains"),
    an honest-risk slide, a timed demo script.
  - **29 of CukaiPandai's last 50 commits are deck/demo polish** — script
    tightening, screenshot recapture, even meme timing on slides. They rehearsed
    at commit granularity.
- Our messaging is dense (ADR references, "verifier-agreed benign look-alikes",
  "pre-registered operating point"). Judges remember sentences, not frontiers.

## Finding 4 — What the podium says the judges rewarded

- **CukaiPandai (2nd):** sovereign Malaysian LLM (ILMU), "0 hallucinated figures —
  the LLM never computes", live Vercel demo, screenshot-rich README, 452 tests.
  Malaysia-localized story + polish + one crisp falsifiable claim.
- **CompliMY (3rd):** integrations judges recognize — Slack bot posting where teams
  already work, Google Docs export, OpenSanctions screening, scraping real SC/BNM
  sources.
- Pattern across all three: (a) a live demo a judge could touch or throw input at,
  (b) a one-sentence Malaysian-market moat, (c) visible integration with familiar
  real-world things (Ollama, ILMU, Slack, Google Docs, a Maybank statement).
  Our goAML XML export was arguably the most regulator-real integration in the
  competition — and XSD validation is the least visible demo moment imaginable.

## Playbook for the next hackathon

1. **Run the real pipeline live** with visible per-agent progress (SSE stream);
   keep the precomputed path as a silent fallback, not the demo.
2. **Accept judge-supplied input** — an upload box or paste field is worth more
   than three governance tabs.
3. **One-sentence moat + three soundbites**, and a human presenter who has
   rehearsed out loud, timed, without a script in hand. Budget the final two days
   for the pitch, not features — the winners' commit logs prove that allocation.
4. **Demo the privacy claim** (local model via Ollama), don't roadmap it.
5. **Lead with the outcome metric** (analyst hours saved, % auto-cleared, 0 leaks),
   bury model accuracy in the appendix.
6. Keep the governance depth — it is real moat for an actual sale — but give each
   invisible feature one *visible* on-stage moment (e.g. open the exported goAML
   XML in the FIU's validator live).
