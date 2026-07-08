"""Hybrid retrieval over the knowledge-base chunks (the R in RAG).

Two rankers, fused: BM25 (lexical) always, plus SEMANTIC cosine over fastembed vectors when
`kb_vectors.npy` is present (built by embed_kb.py — DeepSeek has no embeddings endpoint, so the
embedder is a local ONNX model). The two ranked lists are combined by Reciprocal Rank Fusion, so
semantic recall (paraphrase/synonym matches) and lexical precision reinforce each other. If the
vectors or fastembed are absent, retrieval degrades to lexical-only — nothing breaks. Pure and
deterministic; `retrieve(query, k)` returns top-k passages, each carrying its document + page.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

_KB_DIR = Path(__file__).parent.parent / "data" / "knowledge_base"
_CHUNKS_FILE = _KB_DIR / "kb_chunks.json"
_VECS_FILE = _KB_DIR / "kb_vectors.npy"
_EMBED_MODEL = "BAAI/bge-small-en-v1.5"
_RRF_C = 60  # reciprocal-rank-fusion damping constant (standard)

# Generic words that carry no discriminating signal across AML documents.
_STOPWORDS = frozenset(
    "the a an of and or to in on is are be by with from into then within for that this it its as at "
    "which such any all may must shall should will can not no under over per each other than these "
    "those also more most been being have has had was were would could their they them our we you".split()
)
_K1 = 1.5
_B = 0.75


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z]+", text.lower()) if len(t) > 2 and t not in _STOPWORDS]


@lru_cache(maxsize=1)
def _index() -> tuple[list[dict], list[Counter], dict[str, float], float, list[int]]:
    """Chunks + per-chunk term frequencies + IDF + avg doc length (cached; static file).
    Missing file => empty index (retrieval degrades to no results, never crashes)."""
    chunks: list[dict] = json.loads(_CHUNKS_FILE.read_text(encoding="utf-8")) if _CHUNKS_FILE.exists() else []
    tfs = [Counter(_tokens(c["text"])) for c in chunks]
    df: Counter = Counter()
    for tf in tfs:
        df.update(tf.keys())
    n = len(chunks) or 1
    idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
    lengths = [sum(tf.values()) for tf in tfs]
    avgdl = (sum(lengths) / n) if chunks else 0.0
    return chunks, tfs, idf, avgdl, lengths


def _bm25_scores(query: str) -> dict[int, float]:
    """BM25 score per chunk index for the query (only chunks with a positive score)."""
    _, tfs, idf, avgdl, lengths = _index()
    q_terms = set(_tokens(query))
    scores: dict[int, float] = {}
    for i, tf in enumerate(tfs):
        dl = lengths[i] or 1
        s = 0.0
        for term in q_terms:
            f = tf.get(term, 0)
            if not f:
                continue
            s += idf.get(term, 0.0) * (f * (_K1 + 1)) / (f + _K1 * (1 - _B + _B * dl / avgdl))
        if s > 0:
            scores[i] = s
    return scores


@lru_cache(maxsize=1)
def _semantic_backend():
    """Lazy (model, vectors, numpy) for semantic scoring, or None when unavailable (fastembed
    not installed, or kb_vectors.npy not built) — so retrieval cleanly falls back to lexical."""
    if not _VECS_FILE.exists():
        return None
    try:
        import numpy as np
        from fastembed import TextEmbedding
    except Exception:  # noqa: BLE001 — embedder optional; lexical still works
        return None
    vecs = np.load(_VECS_FILE)
    return TextEmbedding(model_name=_EMBED_MODEL), vecs, np


def _semantic_scores(query: str, topn: int = 50) -> dict[int, float] | None:
    """Cosine similarity of the query to each chunk vector (top-n), or None if unavailable."""
    backend = _semantic_backend()
    if backend is None:
        return None
    model, vecs, np = backend
    q = np.asarray(list(model.embed([query]))[0], dtype=np.float32)
    q /= np.linalg.norm(q) + 1e-8
    sims = vecs @ q  # chunk vectors are pre-normalised => dot == cosine
    idxs = np.argsort(-sims)[:topn]
    return {int(i): float(sims[i]) for i in idxs}


def _fuse(bm25: dict[int, float], semantic: dict[int, float] | None, k: int) -> list[int]:
    """Reciprocal Rank Fusion of the two rankers (lexical always; semantic when present).
    Pure/deterministic — ranks each ranker's hits and sums 1/(c+rank). Ties broken by index."""
    def ranks(scores: dict[int, float]) -> dict[int, int]:
        order = sorted(scores, key=lambda i: (-scores[i], i))
        return {idx: r for r, idx in enumerate(order)}

    bm_rank = ranks(bm25)
    if not semantic:
        return sorted(bm_rank, key=lambda i: (bm_rank[i], i))[:k]
    sem_rank = ranks(semantic)
    candidates = set(bm_rank) | set(sem_rank)

    def rrf(idx: int) -> float:
        s = 0.0
        if idx in bm_rank:
            s += 1.0 / (_RRF_C + bm_rank[idx])
        if idx in sem_rank:
            s += 1.0 / (_RRF_C + sem_rank[idx])
        return s

    return sorted(candidates, key=lambda i: (-rrf(i), i))[:k]


def retrieve(query: str, k: int = 6) -> list[dict]:
    """Top-k KB passages for the query — hybrid BM25 + semantic (RRF) when embeddings are
    available, lexical-only otherwise. Deterministic; each passage carries its source + page."""
    chunks, *_ = _index()
    if not chunks:
        return []
    order = _fuse(_bm25_scores(query), _semantic_scores(query), k)
    return [chunks[i] for i in order]
