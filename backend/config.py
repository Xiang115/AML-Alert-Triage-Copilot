"""Runtime config. Values come from environment / .env (see .env.example).

Model ids are defaults — confirm exact DeepSeek ids before the live run (Phase 2).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Persistence for Decisions + the audit trail (store.py), behind one DATABASE_URL seam.
# Defaults to a SQLite file (zero-ops demo); production points it at a durable Postgres so the
# audit trail survives a redeploy — e.g. a free Neon/Supabase database — with no code change.
_DATA_DIR = Path(__file__).resolve().parent / "data"


def normalize_db_url(url: str) -> str:
    """Bind a hosted-Postgres URL to the installed psycopg3 driver so DATABASE_URL can be
    pasted exactly as Neon / Supabase / Render hand it to you. They give a bare
    `postgres://` or `postgresql://` URL, but SQLAlchemy defaults that to psycopg2 (which we
    don't install) — so map both to the explicit `postgresql+psycopg://` dialect. Any other
    scheme (sqlite, an already-qualified +psycopg URL) is left untouched."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = normalize_db_url(
    os.getenv("DATABASE_URL", f"sqlite:///{(_DATA_DIR / 'app.db').as_posix()}")
)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL_WORKHORSE = os.getenv("MODEL_WORKHORSE", "deepseek-v4-pro")
MODEL_VERIFIER = os.getenv("MODEL_VERIFIER", "deepseek-v4-flash")


def resolve_llm_provider(
    ollama_base_url: str,
    deepseek_base_url: str,
    deepseek_key: str,
    ollama_key: str = "ollama",
) -> tuple[str, str, str]:
    """Choose the active LLM endpoint (Slice B on-prem swap). If OLLAMA_BASE_URL is set, route
    every call to that on-prem OpenAI-compatible endpoint (e.g. Ollama) — customer data never
    leaves the bank, and a local model needs no cloud key. Empty => cloud DeepSeek (the default).
    Pure so the selection is unit-testable without touching the process environment. Returns
    (base_url, api_key, provider_label)."""
    if ollama_base_url:
        return ollama_base_url, ollama_key, "on-prem (Ollama)"
    return deepseek_base_url, deepseek_key, "DeepSeek (cloud)"


# On-prem / provider-swappable model (Slice B). Point OLLAMA_BASE_URL at any OpenAI-compatible
# local endpoint (e.g. http://localhost:11434/v1) to run entirely on-prem; llm.py reads
# LLM_BASE_URL / LLM_API_KEY, so this is a config change, not a code change.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "")
LLM_BASE_URL, LLM_API_KEY, LLM_PROVIDER = resolve_llm_provider(
    OLLAMA_BASE_URL, DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, os.getenv("OLLAMA_API_KEY", "ollama")
)

# LLM client resilience (protects the live /triage run during Q&A). The OpenAI
# SDK retries transient errors (network/429/5xx) with backoff up to MAX_RETRIES,
# and aborts a call that exceeds TIMEOUT_SECONDS rather than hanging on camera.
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
# Offline build tools (precompute, eval) make many reasoning-model calls; a longer
# timeout there lets a valid slow call finish instead of aborting and wasting a full
# retry. The live /triage path keeps the short LLM_TIMEOUT_SECONDS so it fast-fails to
# the precomputed fallback on camera (ADR-0003), rather than hanging on a spinner.
OFFLINE_LLM_TIMEOUT_SECONDS = float(os.getenv("OFFLINE_LLM_TIMEOUT_SECONDS", "180"))

# Verifier flags / triage forces human review below this confidence (ADR-0007).
REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "0.6"))
# A dismiss within this margin above REVIEW_THRESHOLD is flagged "borderline" (ADR-0020) — the
# barely-cleared dismisses most at risk of a wrong clear (contested dismisses are flagged too).
BORDERLINE_MARGIN = float(os.getenv("BORDERLINE_MARGIN", "0.1"))
# The Queue Agent auto-clears (dismisses) a verifier-agreed dismiss only at/above this
# confidence (ADR-0010). Strictly above REVIEW_THRESHOLD so a flagged alert — capped just
# below the review threshold — can never auto-clear; tune from held-out auto-clear precision.
AUTO_CLEAR_THRESHOLD = float(os.getenv("AUTO_CLEAR_THRESHOLD", "0.85"))
# Risk-weighted QA sample of the auto-cleared lane (ADR-0019): the share of auto-cleared alerts
# routed for human spot-check — the operational control for the measured false-negative leakage.
# Ranked by marginal confidence (closest to AUTO_CLEAR_THRESHOLD first). At least 1 when any clear.
QA_SAMPLE_RATE = float(os.getenv("QA_SAMPLE_RATE", "0.2"))
# Adversarial-debate concession gate (ADR-0011/0012). A Triage concession flips the
# disposition; an escalate->dismiss flip is RESISTED when at least this many of the matched
# card's indicators fired — a strong multi-indicator match must not be silently dropped by a
# generic benign hypothesis (it holds as escalate -> needsReview, a human decides). Mirrors the
# cost-sensitive Triage operating point; raise very high to disable the gate.
DEBATE_RESIST_MIN_FIRED = int(os.getenv("DEBATE_RESIST_MIN_FIRED", "2"))
# Fixed for reproducible three-bucket split + eval sampling (ADR-0004/0005).
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
