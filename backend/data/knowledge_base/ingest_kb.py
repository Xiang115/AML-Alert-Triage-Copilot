"""Ingest the knowledge-base PDFs into a retrievable chunk index for live DeepSeek RAG.

A build tool (like ingest_ofac.py / precompute.py): run it manually to (re)build
`kb_chunks.json`, which agents/kb_retrieval.py ranks and agents/coaching.py feeds to
DeepSeek. Extracts per-page text with pypdf, splits each page into overlapping windows,
and tags every chunk with its source document + page so the generated handbook can cite
the real passage. Scanned/image-only PDFs (no text layer) are skipped and reported.

    cd backend && .venv/Scripts/python.exe data/knowledge_base/ingest_kb.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader

_PDF_DIR = Path(__file__).parent / "raw_pdfs"
_OUT = Path(__file__).parent / "kb_chunks.json"

# Human-readable citation label per source file (what the handbook will cite).
_LABELS = {
    "PD_AMLCFTCPF_TFS_FI_Feb2024_v2.pdf": "BNM AML/CFT/CPF PD (Feb 2024)",
    "2025 APG Yearly Typologies Report - for adoption.pdf": "APG Typologies Report (2025)",
    "Professional-Money-Laundering.pdf": "FATF Professional Money Laundering (2018)",
    "fatf_recommendations_2012.pdf": "FATF Recommendations (2012)",
    "comprehensive_update_on_terrorist_financing_risks_2025.pdf": "FATF TF Risks Update (2025)",
    "FinCEN-Advisory-Non-Work-Authorized-Populations.pdf": "FinCEN Advisory",
}

_CHUNK_CHARS = 1100
_OVERLAP = 200


def _clean(text: str) -> str:
    text = text.replace("│", " ")  # box-drawing artefacts from table extraction
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _chunk_page(text: str) -> list[str]:
    """Overlapping windows over one page, split on paragraph/sentence boundaries where possible."""
    text = _clean(text)
    if len(text) < 120:  # skip near-empty pages (headers/footers only)
        return []
    chunks, start = [], 0
    while start < len(text):
        end = start + _CHUNK_CHARS
        if end < len(text):
            # back up to the nearest sentence/newline boundary for a cleaner cut
            window = text[start:end]
            cut = max(window.rfind(". "), window.rfind("\n"))
            if cut > _CHUNK_CHARS // 2:
                end = start + cut + 1
        chunk = text[start:end].strip()
        if len(chunk) >= 120:
            chunks.append(chunk)
        start = max(end - _OVERLAP, end) if end <= start else end - _OVERLAP
    return chunks


def build() -> list[dict]:
    chunks: list[dict] = []
    skipped: list[str] = []
    for pdf in sorted(_PDF_DIR.glob("*.pdf")):
        label = _LABELS.get(pdf.name, pdf.stem)
        try:
            reader = PdfReader(str(pdf))
        except Exception as e:  # noqa: BLE001 — a corrupt PDF shouldn't abort the whole ingest
            skipped.append(f"{pdf.name} (unreadable: {e})")
            continue
        page_chunks = 0
        for pageno, page in enumerate(reader.pages, start=1):
            for text in _chunk_page(page.extract_text() or ""):
                chunks.append({
                    "id": f"{pdf.stem[:24]}-p{pageno}-{page_chunks}",
                    "source": label,
                    "sourceFile": pdf.name,
                    "page": pageno,
                    "text": text,
                })
                page_chunks += 1
        if page_chunks == 0:
            skipped.append(f"{pdf.name} (no text layer — scanned/image PDF)")
    _OUT.write_text(json.dumps(chunks, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Wrote {len(chunks):,} chunks from "
          f"{len({c['sourceFile'] for c in chunks})} PDFs -> {_OUT.name}")
    if skipped:
        print("Skipped (no usable text):")
        for s in skipped:
            print(f"  - {s}")
    return chunks


if __name__ == "__main__":
    build()
