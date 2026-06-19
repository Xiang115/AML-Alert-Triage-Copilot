"""Shared test doubles for the LLM client seam.

`FakeClient` stands in for the OpenAI client (`client.chat.completions.create`),
returning canned JSON strings in order and recording each call's kwargs in
`.calls`. `RaisingClient` simulates a provider outage. Exposed as fixtures so no
test re-defines them (they had already drifted into two variants).
"""

import pytest


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
