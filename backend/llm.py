"""Provider-agnostic LLM client. DeepSeek via its OpenAI-compatible endpoint,
temperature 0 (ADR-0003). The client is injectable so tests run without tokens.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, ValidationError

import config

logger = logging.getLogger("llm")

T = TypeVar("T", bound=BaseModel)

_client = None
_capture: ContextVar[dict | None] = ContextVar("copilot_run_capture", default=None)


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
    # LLM_BASE_URL / LLM_API_KEY select the active provider (Slice B): cloud DeepSeek by default,
    # or an on-prem OpenAI-compatible endpoint when OLLAMA_BASE_URL is set — same client, no code change.
    return _make_openai(
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
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


def _sha256(text: str | None) -> str:
    return "sha256:" + hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _redact_prompt(text: str | None) -> str:
    if not text:
        return ""
    out = re.sub(r"Account: .+? \(", "Account: [REDACTED] (", text)
    out = re.sub(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+)", "[EMAIL_REDACTED]", out)
    out = re.sub(r"\b\d{10,18}\b", "[LONG_NUMBER_REDACTED]", out)
    return out


def begin_run_capture(alert_id: str, *, mode: str, semantic: bool = False) -> str:
    """Start per-request LLM envelope capture for the live copilot run."""
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    now = datetime.now().astimezone()
    _capture.set({
        "runId": run_id,
        "alertId": alert_id,
        "mode": mode,
        "semantic": semantic,
        "provider": config.LLM_PROVIDER,
        "model": config.MODEL_WORKHORSE,
        "status": "running",
        "startedAt": now.isoformat(),
        "completedAt": None,
        "latencyMs": None,
        "_startedPerf": time.perf_counter(),
        "llmCalls": [],
        "redactions": [
            "Account holder names are redacted in captured prompts.",
            "Long account-like numeric strings and email addresses are redacted.",
            "Raw content hashes are retained so privileged reviewers can reconcile the unredacted audit copy.",
        ],
    })
    return run_id


def current_run_capture() -> dict | None:
    return _capture.get()


def finish_run_capture(status: str, *, final_output: dict | None = None, error: str | None = None) -> dict | None:
    capture = _capture.get()
    if capture is None:
        return None
    now = datetime.now().astimezone()
    capture["status"] = status
    capture["completedAt"] = now.isoformat()
    capture["latencyMs"] = round((time.perf_counter() - capture["_startedPerf"]) * 1000)
    capture["finalOutput"] = final_output
    capture["error"] = error
    capture.pop("_startedPerf", None)
    _capture.set(None)
    return capture


def _record_llm_call(
    *,
    stage: str,
    template_id: str,
    model: str,
    response_model: str,
    attempt: int,
    messages: list[dict],
    content: str | None,
    schema_valid: bool,
    validation_error: str | None = None,
) -> None:
    capture = _capture.get()
    if capture is None:
        return
    capture["llmCalls"].append({
        "stage": stage,
        "templateId": template_id,
        "model": model,
        "responseModel": response_model,
        "attempt": attempt,
        "messages": [
            {
                "role": m["role"],
                "content": _redact_prompt(m["content"]),
                "contentHash": _sha256(m["content"]),
                "redactionLevel": "piiRedacted",
            }
            for m in messages
        ],
        "rawResponse": content or "",
        "rawResponseHash": _sha256(content),
        "schemaValid": schema_valid,
        "validationError": validation_error,
    })


def complete_model(
    system: str,
    user: str,
    model: str,
    response_model: type[T],
    *,
    client=None,
    max_tokens: int = 8192,
    temperature: float = 0.0,
    stage: str | None = None,
    template_id: str | None = None,
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
            parsed = response_model.model_validate_json(content)
            _record_llm_call(
                stage=stage or response_model.__name__,
                template_id=template_id or response_model.__name__,
                model=model,
                response_model=response_model.__name__,
                attempt=attempt + 1,
                messages=messages,
                content=content,
                schema_valid=True,
            )
            return parsed
        except (ValidationError, ValueError, TypeError) as e:
            last_err = e
            _record_llm_call(
                stage=stage or response_model.__name__,
                template_id=template_id or response_model.__name__,
                model=model,
                response_model=response_model.__name__,
                attempt=attempt + 1,
                messages=messages,
                content=content,
                schema_valid=False,
                validation_error=str(e),
            )
            logger.warning(
                "Model %s reply failed %s validation on attempt %d: %s",
                model, response_model.__name__, attempt + 1, e,
            )
    raise ValueError(
        f"Model did not return a valid {response_model.__name__} after retry: {last_err}"
    )
