"""Shared test doubles for the LLM client seam + global state isolation.

`FakeClient` stands in for the OpenAI client (`client.chat.completions.create`),
returning canned JSON strings in order and recording each call's kwargs in
`.calls`. `RaisingClient` simulates a provider outage. Exposed as fixtures so no
test re-defines them (they had already drifted into two variants).

The DATABASE_URL defaults to in-memory SQLite ('sqlite://') BEFORE any import of
config/main, so the suite never touches a real db file — unless DATABASE_URL is already
set (e.g. a Postgres URL to run the suite against a real RDBMS, `setdefault` keeps it).
`_reset_state` (autouse) isolates the per-test mutations to the alert catalog + the store.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")  # in-memory; must precede config/main import

import pytest


@pytest.fixture(autouse=True)
def _reset_state():
    """Isolate each test: endpoints mutate the persisted store (an alert's status/STR, the
    decisions table, the audit trail). store.reset() restores the seeded alert catalog +
    audit seed and drops session decisions after each test."""
    import main

    yield
    main.store.reset()
    main.app.dependency_overrides.clear()


class FakeResponse:
    """Mimics an OpenAI chat completion: `.choices[0].message.content`."""

    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]


class FakeClient:
    """Returns canned `contents` in order; records each create(**kwargs) in `.calls`."""

    def __init__(self, contents):
        self._contents = list(contents)
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self._contents.pop(0))


class RaisingClient:
    """Simulates a provider outage: every call raises."""

    def __init__(self):
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        raise RuntimeError("simulated provider outage")


@pytest.fixture
def make_client():
    """Factory: `make_client([json1, json2, ...])` -> a FakeClient."""

    def _make(contents):
        return FakeClient(contents)

    return _make


@pytest.fixture
def raising_client():
    """A client whose every call raises (provider-outage path)."""
    return RaisingClient()
