"""verifier tests use a fake client — no DeepSeek calls, no tokens."""

import json

from agents.knowledge_base import get_card
from agents.verifier import verify


class _Resp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]


class FakeClient:
    def __init__(self, contents):
        self._contents = list(contents)
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Resp(self._contents.pop(0))


def test_disagreement_flags_for_human_review():
    card = get_card("FI-01")
    out = verify(
        "evidence block",
        "escalate",
        card,
        client=FakeClient([json.dumps({"agreesWithRecommendation": False, "note": "Could be a small business."})]),
    )
    assert out["status"] == "flagged"
    assert out["agreesWithRecommendation"] is False
    assert out["note"]


def test_agreement_passes_through():
    card = get_card("PT-01")
    out = verify(
        "evidence block",
        "escalate",
        card,
        client=FakeClient([json.dumps({"agreesWithRecommendation": True, "note": "Evidence clearly meets the test."})]),
    )
    assert out["status"] == "agreed"
    assert out["agreesWithRecommendation"] is True
