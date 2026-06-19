"""Provider-agnostic LLM client. DeepSeek via its OpenAI-compatible endpoint,
temperature 0 (ADR-0003). The client is injectable so tests run without tokens.
"""

from __future__ import annotations

import json
import logging

import config

logger = logging.getLogger("llm")

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


def complete_json(
    system: str,
    user: str,
    model: str,
    *,
    client=None,
    max_tokens: int = 2048,
    temperature: float = 0.0,
) -> dict:
    """Call the model and parse a JSON object response. Retries once on invalid JSON.

    Note: DeepSeek V4 (pro/flash) emits hidden reasoning tokens that count against
    max_tokens — observed ~1500 on a full 5-card triage prompt. Budget generously or
    the visible JSON gets truncated to empty; the 2048 default leaves headroom. STR
    drafting (longer output) should pass a higher max_tokens.
    """
    client = client or _default_client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_err = None
    for attempt in range(2):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError) as e:
            last_err = e
            logger.warning("Model %s returned non-JSON on attempt %d: %s", model, attempt + 1, e)
    raise ValueError(f"Model did not return valid JSON after retry: {last_err}")
