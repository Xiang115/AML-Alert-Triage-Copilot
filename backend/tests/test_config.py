"""DATABASE_URL normalization: a hosted-Postgres URL must work pasted in as-is."""

import pytest

from config import normalize_db_url


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
