"""DATABASE_URL normalization: a hosted-Postgres URL must work pasted in as-is."""

import pytest

from config import normalize_db_url, resolve_llm_provider


@pytest.mark.parametrize("raw,expected", [
    # Neon/Supabase/Render hand you a bare postgres scheme — bind it to psycopg3.
    ("postgresql://u:p@ep-x.neon.tech/db", "postgresql+psycopg://u:p@ep-x.neon.tech/db"),
    ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    # query params (e.g. Neon's sslmode=require) are preserved.
    ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
    # already-qualified or non-postgres schemes are left untouched.
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("sqlite:///data/app.db", "sqlite:///data/app.db"),
    ("sqlite://", "sqlite://"),
])
def test_normalize_db_url(raw, expected):
    assert normalize_db_url(raw) == expected


def test_resolve_llm_provider_defaults_to_cloud_deepseek():
    base, key, provider = resolve_llm_provider("", "https://api.deepseek.com/v1", "sk-live")
    assert base == "https://api.deepseek.com/v1"
    assert key == "sk-live"
    assert "DeepSeek" in provider


def test_resolve_llm_provider_switches_to_onprem_when_set():
    # OLLAMA_BASE_URL set => route to the local endpoint with no cloud key (customer data stays on-prem)
    base, key, provider = resolve_llm_provider(
        "http://localhost:11434/v1", "https://api.deepseek.com/v1", "sk-live")
    assert base == "http://localhost:11434/v1"
    assert key == "ollama"  # a local model needs no cloud credential
    assert "on-prem" in provider.lower()
