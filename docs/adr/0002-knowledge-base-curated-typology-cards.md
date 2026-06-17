# Knowledge base is curated typology cards, not PDF RAG

The agents need to ground triage and verification in the 5 encoded transaction typologies
(pass-through, fan-in/fan-out, structuring, dormant-then-active, KYC mismatch). The raw PDFs we
collected are large thematic FATF reports (proliferation financing 45 MB, terrorist financing, CSAE,
the 40 Recommendations) — they are not a catalog of those typologies. We decided to hand-author a
tiny set of structured **typology cards** (`backend/data/typologies/typologies.json`) as the
retrieval unit, and demote the PDFs to citation anchors only.

Why: cards are tiny, deterministic, and demo-safe, and each card's `distinguishingTest` doubles as
the Verifier's checklist. Embedding the PDFs into a vector store (the path initially being built)
would surface off-topic proliferation/TF text, be non-deterministic on the demo path, and burn
timeline — exactly the "real RAG stack" the project guardrails warn against.

Rejected: chunk+embed all PDFs (off-topic retrieval, non-deterministic, slow). Parked as stretch: a
hybrid that embeds only the 2 adjacent PDFs for extra Q&A grounding.
