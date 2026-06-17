"""Provider-agnostic LLM client. DeepSeek via its OpenAI-compatible endpoint,
temperature 0 (ADR-0003). The client is injectable so tests run without tokens.
"""

from __future__ import annotations

import json

import config

_client = None


def _default_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)
    return _client


def complete_json(
    system: str,
    user: str,
    model: str,
    *,
    client=None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> dict:
    """Call the model and parse a JSON object response. Retries once on invalid JSON.

    Note: DeepSeek V4 (pro/flash) emits hidden reasoning tokens that count against
    max_tokens. Budget generously (>= a few hundred) or the visible JSON gets
    truncated to empty. The 1024 default is comfortable for our triage/STR outputs.
    """
    client = client or _default_client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_err = None
    for _ in range(2):
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
    raise ValueError(f"Model did not return valid JSON after retry: {last_err}")
