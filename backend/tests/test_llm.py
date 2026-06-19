"""llm.py unit tests use a fake client — they never call DeepSeek (no tokens)."""

import pytest

import config
import llm
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


def test_default_client_configures_timeout_and_retries(monkeypatch):
    """The real client is built with a request timeout and bounded retries so the
    live /triage run cannot hang or die on a transient provider blip during Q&A."""
    captured = {}

    def fake_make(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(llm, "_make_openai", fake_make)
    monkeypatch.setattr(llm, "_client", None)

    llm._default_client()

    assert captured["timeout"] == config.LLM_TIMEOUT_SECONDS
    assert captured["max_retries"] == config.LLM_MAX_RETRIES
    assert captured["base_url"] == config.DEEPSEEK_BASE_URL
