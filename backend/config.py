"""Runtime config. Values come from environment / .env (see .env.example).

Model ids are defaults — confirm exact DeepSeek ids before the live run (Phase 2).
"""

import os

from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL_WORKHORSE = os.getenv("MODEL_WORKHORSE", "deepseek-v4-pro")
MODEL_VERIFIER = os.getenv("MODEL_VERIFIER", "deepseek-v4-flash")

# LLM client resilience (protects the live /triage run during Q&A). The OpenAI
# SDK retries transient errors (network/429/5xx) with backoff up to MAX_RETRIES,
# and aborts a call that exceeds TIMEOUT_SECONDS rather than hanging on camera.
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))

# Verifier flags / triage forces human review below this confidence (ADR-0007).
REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "0.6"))
# Fixed for reproducible three-bucket split + eval sampling (ADR-0004/0005).
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
