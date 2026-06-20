"""llm.py unit tests use a fake client — they never call DeepSeek (no tokens)."""

import json

import pytest

import config
import llm
from llm import complete_model
from schemas import LLMResponse


class _Probe(LLMResponse):
    """A tiny response model standing in for a real agent's expected shape."""

    recommendation: str
    explanation: str = ""


def test_complete_model_returns_validated_instance(make_client):
    fake = make_client([json.dumps({"recommendation": "escalate", "explanation": "in then out"})])
    out = complete_model("sys", "user", "deepseek-v4-pro", _Probe, client=fake)
    assert isinstance(out, _Probe)
    assert out.recommendation == "escalate"
    assert out.explanation == "in then out"


def test_complete_model_ignores_extra_keys(make_client):
    # The model invents a stray field; that must not fail the parse.
    fake = make_client([json.dumps({"recommendation": "dismiss", "chatter": "here is my answer"})])
    out = complete_model("s", "u", "m", _Probe, client=fake)
    assert out.recommendation == "dismiss"
    assert len(fake.calls) == 1  # no retry needed


def test_complete_model_retries_once_on_bad_json(make_client):
    fake = make_client(["not json {", json.dumps({"recommendation": "escalate"})])
    out = complete_model("s", "u", "m", _Probe, client=fake)
    assert out.recommendation == "escalate"
    assert len(fake.calls) == 2


def test_complete_model_retries_on_valid_json_wrong_shape(make_client):
    # Valid JSON, but the required `recommendation` is missing — the failure that
    # used to surface as an unhandled KeyError in the agents. Now it retries.
    fake = make_client([json.dumps({"explanation": "no recommendation here"}),
                        json.dumps({"recommendation": "dismiss"})])
    out = complete_model("s", "u", "m", _Probe, client=fake)
    assert out.recommendation == "dismiss"
    assert len(fake.calls) == 2


def test_complete_model_raises_value_error_after_retry_exhausted(make_client):
    # Both replies are the wrong shape — caller gets a clean ValueError, never a
    # raw KeyError/ValidationError leaking from the provider's reply.
    fake = make_client([json.dumps({}), json.dumps({"explanation": "still wrong"})])
    with pytest.raises(ValueError):
        complete_model("s", "u", "m", _Probe, client=fake)
    assert len(fake.calls) == 2


def test_complete_model_retries_on_empty_body(make_client):
    # DeepSeek V4 can return an empty/None body under reasoning-token starvation
    # (the documented reason for retrying); that must retry, not raise TypeError.
    fake = make_client([None, json.dumps({"recommendation": "escalate"})])
    out = complete_model("s", "u", "m", _Probe, client=fake)
    assert out.recommendation == "escalate"
    assert len(fake.calls) == 2


def test_complete_model_enforces_settings(make_client):
    fake = make_client([json.dumps({"recommendation": "escalate"})])
    complete_model("sys", "user", "deepseek-v4-pro", _Probe, client=fake, max_tokens=3000)
    assert fake.calls[0]["temperature"] == 0.0
    assert fake.calls[0]["model"] == "deepseek-v4-pro"
    assert fake.calls[0]["response_format"] == {"type": "json_object"}
    assert fake.calls[0]["max_tokens"] == 3000


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
