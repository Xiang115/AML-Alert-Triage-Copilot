"""llm.py unit tests use a fake client — they never call DeepSeek (no tokens)."""

import pytest

from llm import complete_json


def test_complete_json_parses_and_enforces_settings(make_client):
    fake = make_client(['{"recommendation": "escalate", "confidence": 0.9}'])
    out = complete_json("sys", "user", "deepseek-v4-pro", client=fake)
    assert out["recommendation"] == "escalate"
    assert fake.calls[0]["temperature"] == 0.0
    assert fake.calls[0]["model"] == "deepseek-v4-pro"
    assert fake.calls[0]["response_format"] == {"type": "json_object"}


def test_complete_json_retries_once_on_bad_json(make_client):
    fake = make_client(["not json {", '{"ok": true}'])
    out = complete_json("s", "u", "m", client=fake)
    assert out["ok"] is True
    assert len(fake.calls) == 2


def test_complete_json_raises_after_retry_exhausted(make_client):
    fake = make_client(["bad", "still bad"])
    with pytest.raises(ValueError):
        complete_json("s", "u", "m", client=fake)
    assert len(fake.calls) == 2
