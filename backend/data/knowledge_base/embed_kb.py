"""Embed the KB chunks for SEMANTIC retrieval (the S in hybrid RAG).

Optional build step (run after ingest_kb.py). Requires `fastembed` — an ONNX embedder — because
DeepSeek has no embeddings endpoint. Writes `kb_vectors.npy`: one L2-normalised row per chunk in
kb_chunks.json order, so agents/kb_retrieval can cosine-rank by a single dot product and FUSE with
BM25. If this file is absent, retrieval degrades to lexical-only — nothing breaks.

    cd backend && .venv/Scripts/python.exe data/knowledge_base/embed_kb.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

_KB = Path(__file__).parent
_CHUNKS = _KB / "kb_chunks.json"
_VECS = _KB / "kb_vectors.npy"
MODEL_NAME = "BAAI/bge-small-en-v1.5"  # small, CPU-friendly, 384-dim


def build() -> None:
    chunks = json.loads(_CHUNKS.read_text(encoding="utf-8"))
    texts = [c["text"] for c in chunks]
    model = TextEmbedding(model_name=MODEL_NAME)
    vecs = np.array(list(model.embed(texts)), dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8  # normalise => cosine via dot
    np.save(_VECS, vecs)
    print(f"Embedded {len(chunks):,} chunks -> {_VECS.name}  shape={vecs.shape}  model={MODEL_NAME}")


if __name__ == "__main__":
    build()
