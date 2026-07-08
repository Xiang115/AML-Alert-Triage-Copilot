"""RAG analyst-handbook tests: retrieval is exercised for real; generation uses a fake client."""

import json

from agents.coaching import generate_handbook
from agents.kb_retrieval import retrieve
from agents.knowledge_base import get_card
from schemas import CoachingHandbook


def test_retrieve_returns_page_tagged_passages():
    hits = retrieve("cash deposits structured just below the reporting threshold", k=5)
    assert hits, "BM25 retrieval returned nothing over the KB chunks"
    for c in hits:
        assert c["text"] and c["source"] and c["page"]  # each carries a citable source + page


def test_retrieve_is_deterministic():
    q = "money mule funnel account rapid onward transfer"
    assert [c["id"] for c in retrieve(q, k=6)] == [c["id"] for c in retrieve(q, k=6)]


def test_fuse_lexical_only_orders_by_bm25_rank():
    # no semantic vectors => pure BM25 order (the fallback path)
    from agents.kb_retrieval import _fuse
    assert _fuse({5: 3.0, 2: 2.0, 9: 1.0}, None, k=2) == [5, 2]


def test_fuse_rrf_rewards_agreement_across_rankers():
    # a chunk ranked top by BOTH lexical and semantic should win over one strong in only one
    from agents.kb_retrieval import _fuse
    bm25 = {7: 5.0, 1: 4.0, 2: 3.0}
    semantic = {7: 0.9, 3: 0.8, 4: 0.7}
    assert _fuse(bm25, semantic, k=1) == [7]


def test_generate_handbook_grounds_checks_in_retrieved_sources(make_client):
    # the model is faked; retrieval is real, so the excerpts it "used" are genuine KB passages
    fake = make_client([json.dumps({"whatToCheck": [
        {"check": "Confirm the cash deposits cluster just below RM25,000 across branches.", "source": 1},
        {"check": "Check whether consolidated funds are forwarded onward within a short window.", "source": 2},
    ]})])
    hb = generate_handbook(get_card("ST-01"), client=fake)

    assert isinstance(hb, CoachingHandbook)
    assert hb.typology_code == "ST-01"
    assert len(hb.what_to_check) == 2
    assert all(c.check and c.source for c in hb.what_to_check)  # each check cites a real source+page
    assert hb.sources  # the documents consulted
    # the retrieved KB excerpts were actually sent to the model (real RAG, not free generation)
    user_msg = fake.calls[0]["messages"][1]["content"]
    assert "SOURCE EXCERPTS" in user_msg
    assert "p." in user_msg


def test_generate_handbook_tolerates_a_bad_source_index(make_client):
    # the model cites an out-of-range excerpt number — must not crash, just degrade the citation
    fake = make_client([json.dumps({"whatToCheck": [{"check": "Do the thing.", "source": 99}]})])
    hb = generate_handbook(get_card("PT-01"), client=fake)
    assert hb.what_to_check[0].source  # falls back to a generic label, never an index error
