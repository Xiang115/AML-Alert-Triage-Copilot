"""On-prem hardening: prove the provider swap actually routes to a local OpenAI-compatible
endpoint over HTTP — not merely that `_make_openai` received the right kwargs. Stands up a tiny
local server (no real model) and drives `complete_model` through the REAL OpenAI client, so the
"customer data never leaves the bank" claim is demonstrated end-to-end, not just asserted.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import config
import llm
from llm import complete_model
from schemas import LLMResponse

_RECEIVED: list[dict] = []


class _Probe(LLMResponse):
    recommendation: str


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the test output clean
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        _RECEIVED.append({
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "body": json.loads(body or b"{}"),
        })
        payload = {
            "id": "chatcmpl-local", "object": "chat.completion", "created": 0, "model": "local-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"recommendation": "escalate"})}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def local_openai_server():
    _RECEIVED.clear()
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_onprem_swap_routes_a_real_request_to_the_local_endpoint(monkeypatch, local_openai_server):
    # Point the provider swap at the local server (as OLLAMA_BASE_URL would) and use the REAL client.
    base = f"http://127.0.0.1:{local_openai_server}/v1"
    monkeypatch.setattr(config, "LLM_BASE_URL", base)
    monkeypatch.setattr(config, "LLM_API_KEY", "ollama")

    client = llm._build_client(timeout=10)
    out = complete_model("system", "user", "local-model", _Probe, client=client)

    # the reply parsed AND the request actually reached the local endpoint (not DeepSeek)
    assert out.recommendation == "escalate"
    assert _RECEIVED, "the on-prem endpoint received no request"
    assert _RECEIVED[0]["path"].endswith("/chat/completions")
    assert _RECEIVED[0]["auth"] == "Bearer ollama"      # the on-prem key was sent
    assert _RECEIVED[0]["body"]["model"] == "local-model"
