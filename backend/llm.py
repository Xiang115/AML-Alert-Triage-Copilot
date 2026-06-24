"""Provider-agnostic LLM client. DeepSeek via its OpenAI-compatible endpoint,
temperature 0 (ADR-0003). The client is injectable so tests run without tokens.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

import config

logger = logging.getLogger("llm")

T = TypeVar("T", bound=BaseModel)

_client = None


def coerce_text(v):
    """Coerce a free-text field the model may have returned as a dict/list into readable prose.

    DeepSeek (esp. flash) often answers a "reasoning" field with a structured object or a list of
    points instead of a plain string. Rather than fail validation and burn a full retry, flatten it
    to "key: value; key: value" / "a; b". Strings pass through unchanged. Use as a mode="before"
    field validator on untrusted free-text fields."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return "; ".join(f"{k}: {coerce_text(val)}" for k, val in v.items())
    if isinstance(v, (list, tuple)):
        return "; ".join(coerce_text(x) for x in v)
    return str(v)


def _make_openai(**kwargs):
    """Seam for tests: builds the real OpenAI client (imported lazily so the
    dependency isn't required when a fake client is injected)."""
    from openai import OpenAI

    return OpenAI(**kwargs)


def _build_client(timeout: float):
    return _make_openai(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        timeout=timeout,
        max_retries=config.LLM_MAX_RETRIES,
    )


def _default_client():
    """Memoized real client, hardened for the live /triage run: a per-request
    timeout so a slow provider can't hang the demo, and bounded SDK retries
    (exponential backoff on network/429/5xx) so a transient blip self-heals."""
    global _client
    if _client is None:
        _client = _build_client(config.LLM_TIMEOUT_SECONDS)
    return _client


def use_offline_timeout() -> None:
    """Switch the shared client to the longer OFFLINE timeout (config) for build tools
    (precompute, eval). Those make many reasoning-model calls where the short live
    timeout would abort valid-but-slow calls and waste a full retry. Call once at the
    start of an offline run; the live /triage path keeps the short timeout."""
    global _client
    _client = _build_client(config.OFFLINE_LLM_TIMEOUT_SECONDS)


def _log_cache_usage(resp, model: str) -> None:
    """Surface DeepSeek's prompt-cache hit/miss tokens (when present) so the reuse
    of the static typology prefix is verifiable. No-op for clients without usage."""
    usage = getattr(resp, "usage", None)
    hit = getattr(usage, "prompt_cache_hit_tokens", None)
    miss = getattr(usage, "prompt_cache_miss_tokens", None)
    if hit is not None or miss is not None:
        logger.info("prompt cache: hit=%s miss=%s (%s)", hit, miss, model)


def complete_model(
    system: str,
    user: str,
    model: str,
    response_model: type[T],
    *,
    client=None,
    max_tokens: int = 8192,
    temperature: float = 0.0,
) -> T:
    """Call the model and parse its reply into `response_model`, a validated instance.

    This is the seam where *untrusted* model output crosses into the typed domain.
    The retry loop covers both failure modes a model exhibits: invalid JSON, and
    valid JSON of the wrong shape (a missing required field). Either retries once;
    a clean `ValueError` is raised after the retry is exhausted, so callers never
    have to handle a raw `KeyError`/`ValidationError` from the provider's reply.

    Note: DeepSeek V4 (pro/flash) emits hidden reasoning tokens that count against
    max_tokens — observed ~1500 on a full 5-card triage prompt, and occasionally far
    more, which truncates the visible JSON to empty (an EOF parse error) and forces a
    full retry — the main source of wasted calls. Budget generously: the 8192 default is
    a CAP, not a cost (the model only generates what it needs), so sizing it well above
    the reasoning burst removes the truncation-retries without changing reasoning quality.
    """
    client = client or _default_client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_err: Exception | None = None
    for attempt in range(2):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        _log_cache_usage(resp, model)
        try:
            return response_model.model_validate_json(content)
        except (ValidationError, ValueError, TypeError) as e:
            last_err = e
            logger.warning(
                "Model %s reply failed %s validation on attempt %d: %s",
                model, response_model.__name__, attempt + 1, e,
            )
    raise ValueError(
        f"Model did not return a valid {response_model.__name__} after retry: {last_err}"
    )
