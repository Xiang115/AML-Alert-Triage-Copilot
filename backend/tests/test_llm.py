"""llm.py unit tests use a fake client — they never call DeepSeek (no tokens)."""

import pytest

from llm import complete_json


class _Resp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]


class FakeClient:
    """Stands in for the OpenAI client: client.chat.completions.create(...)."""

    def __init__(self, contents):
        self._contents = list(contents)
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Resp(self._contents.pop(0))


def test_complete_json_parses_and_enforces_settings():
    fake = FakeClient(['{"recommendation": "escalate", "confidence": 0.9}'])
    out = complete_json("sys", "user", "deepseek-v4-pro", client=fake)
    assert out["recommendation"] == "escalate"
    assert fake.calls[0]["temperature"] == 0.0
    assert fake.calls[0]["model"] == "deepseek-v4-pro"
    assert fake.calls[0]["response_format"] == {"type": "json_object"}


def test_complete_json_retries_once_on_bad_json():
    fake = FakeClient(["not json {", '{"ok": true}'])
    out = complete_json("s", "u", "m", client=fake)
    assert out["ok"] is True
    assert len(fake.calls) == 2


def test_complete_json_raises_after_retry_exhausted():
    fake = FakeClient(["bad", "still bad"])
    with pytest.raises(ValueError):
        complete_json("s", "u", "m", client=fake)
    assert len(fake.calls) == 2
