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


def _make_openai(**kwargs):
    """Seam for tests: builds the real OpenAI client (imported lazily so the
    dependency isn't required when a fake client is injected)."""
    from openai import OpenAI

    return OpenAI(**kwargs)


def _default_client():
    """Memoized real client, hardened for the live /triage run: a per-request
    timeout so a slow provider can't hang the demo, and bounded SDK retries
    (exponential backoff on network/429/5xx) so a transient blip self-heals."""
    global _client
    if _client is None:
        _client = _make_openai(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            timeout=config.LLM_TIMEOUT_SECONDS,
            max_retries=config.LLM_MAX_RETRIES,
        )
    return _client


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
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> T:
    """Call the model and parse its reply into `response_model`, a validated instance.

    This is the seam where *untrusted* model output crosses into the typed domain.
    The retry loop covers both failure modes a model exhibits: invalid JSON, and
    valid JSON of the wrong shape (a missing required field). Either retries once;
    a clean `ValueError` is raised after the retry is exhausted, so callers never
    have to handle a raw `KeyError`/`ValidationError` from the provider's reply.

    Note: DeepSeek V4 (pro/flash) emits hidden reasoning tokens that count against
    max_tokens — observed ~1500 on a full 5-card triage prompt, and occasionally more,
    which truncates the visible JSON to empty (an EOF parse error mid-batch). Budget
    generously; the 4096 default leaves headroom for reasoning + the JSON. STR drafting
    (longer output) should pass a higher max_tokens.
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
