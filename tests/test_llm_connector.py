import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
from pathlib import Path
import sys
import threading

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
llm = importlib.import_module("comfyui_skill_prompt.llm_connector")
routes = importlib.import_module("comfyui_skill_prompt.connector_api")


@pytest.mark.parametrize("address,base", [
    ("https://api.venice.ai/api/v1", "https://api.venice.ai/api/v1"),
    ("https://api.venice.ai/api/v1/chat/completions/", "https://api.venice.ai/api/v1"),
    ("https://provider.test/v1/models", "https://provider.test/v1"),
    ("https://provider.test", "https://provider.test/v1"),
    ("http://127.0.0.1:1234/v1", "http://127.0.0.1:1234/v1"),
    ("https://provider.test/compatible-mode/v1", "https://provider.test/compatible-mode/v1"),
    ("https://provider.test/chat/completions", "https://provider.test"),
])
def test_api_addresses(address, base):
    assert llm.api_endpoints(address) == (base + "/chat/completions", base + "/models")


class Response:
    def __init__(self, status, data):
        self.status_code = status
        self.data = data

    def json(self):
        return self.data


def test_manual_key_payload_and_multimodal_messages(monkeypatch):
    calls = []
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response(200, {"choices": [{"message": {"content": "<think>internal</think> final prompt"}}]})
    monkeypatch.setattr(llm.requests, "request", request)
    connector = llm.SimpleLLMConnector("https://provider.test/v1", " Bearer my-manual-key ", " vision-model ")
    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,test", "detail": "auto"}},
        {"type": "text", "text": "describe"},
    ]}]
    assert connector.invoke(messages, seed=5, max_tokens=100) == "final prompt"
    request = calls[0][2]
    assert request["headers"]["Authorization"] == "Bearer my-manual-key"
    payload = request["json"]
    assert payload["model"] == "vision-model"
    assert payload["seed"] == 5 and payload["max_tokens"] == 100
    assert "response_format" not in payload and "top_k" not in payload
    assert "detail" not in payload["messages"][0]["content"][0]["image_url"]
    assert messages[0]["content"][0]["image_url"]["detail"] == "auto"
    assert "my-manual-key" not in connector.get_state()


def test_unsupported_parameters_are_adapted_only_after_rejection(monkeypatch):
    payloads = []
    def request(method, url, **kwargs):
        payloads.append(dict(kwargs["json"]))
        if "seed" in kwargs["json"]:
            return Response(400, {"error": {"param": "seed", "message": "Unsupported parameter: seed"}})
        if "max_tokens" in kwargs["json"]:
            return Response(400, {"error": {"message": "max_tokens is not supported. Use max_completion_tokens instead."}})
        return Response(200, {"choices": [{"message": {"content": "OK"}}]})
    monkeypatch.setattr(llm.requests, "request", request)
    connector = llm.SimpleLLMConnector("https://provider.test/v1", "", "model")
    assert connector.invoke([], max_tokens=80, seed=42) == "OK"
    assert len(payloads) == 3
    assert payloads[-1]["max_completion_tokens"] == 80
    assert "seed" not in payloads[-1]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_errors_are_not_retried_and_do_not_echo_key(monkeypatch, status):
    calls = []
    def request(*args, **kwargs):
        calls.append(1)
        return Response(status, {"error": {"message": "Invalid credential: secret-token"}})
    monkeypatch.setattr(llm.requests, "request", request)
    with pytest.raises(ValueError) as error:
        llm.SimpleLLMConnector("https://provider.test", "secret-token", "model").invoke([])
    assert f"HTTP {status}" in str(error.value)
    assert "secret-token" not in str(error.value)
    assert len(calls) == 1


def test_timeout_does_not_repeat_generation(monkeypatch):
    calls = []
    def request(*args, **kwargs):
        calls.append(1)
        raise requests.Timeout()
    monkeypatch.setattr(llm.requests, "request", request)
    with pytest.raises(ValueError, match="连接超时"):
        llm.SimpleLLMConnector("http://localhost:1234/v1", "", "model").invoke([])
    assert len(calls) == 1


def test_reasoning_is_not_used_as_prompt_when_content_empty(monkeypatch):
    monkeypatch.setattr(llm.requests, "request", lambda *args, **kwargs: Response(200, {
        "choices": [{"message": {"content": "", "reasoning_content": "internal reasoning"}, "finish_reason": "length"}]}))
    with pytest.raises(ValueError, match="max_tokens"):
        llm.SimpleLLMConnector("https://provider.test", "", "model").invoke([])
    result = llm.SimpleLLMConnector("https://provider.test", "", "model").test_connection()
    assert result["ok"] and "API 已响应" in result["reply"]


@pytest.fixture
def mock_provider():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, data):
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            calls.append((self.path, self.headers.get("Authorization"), None))
            self.send_json({"data": [{"id": "vision"}, {"id": "chat"}, {"id": "chat"}]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, self.headers.get("Authorization"), body))
            self.send_json({"choices": [{"message": {"content": "OK"}}]})
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/api/v1", calls
    server.shutdown()
    server.server_close()
    thread.join()


def test_real_http_model_listing_and_connection_test(mock_provider):
    base, calls = mock_provider
    connector = llm.SimpleLLMConnector(base, "local-test-key", "chat", timeout=5)
    assert connector.list_models() == ["chat", "vision"]
    result = connector.test_connection()
    assert result["ok"] and result["reply"] == "OK"
    assert [call[0] for call in calls] == ["/api/v1/models", "/api/v1/chat/completions"]
    assert all(call[1] == "Bearer local-test-key" for call in calls)
    assert calls[-1][2]["max_tokens"] == 64


def test_button_routes_use_current_values(mock_provider):
    base, calls = mock_provider
    class Request:
        async def json(self):
            return {"base_url": base, "api_key": "button-key", "model": "vision", "timeout": 5}
    models = asyncio.run(routes.get_models(Request()))
    assert json.loads(models.text) == {"ok": True, "models": ["chat", "vision"]}
    result = asyncio.run(routes.test_connection(Request()))
    assert json.loads(result.text)["model"] == "vision"
    assert all(call[1] == "Bearer button-key" for call in calls)


def test_connector_node_socket_matches_skill_generator():
    connector = llm.SkillLLMServiceConnector.execute("https://provider.test/v1", "manual", "model")[0]
    assert isinstance(connector, llm.SimpleLLMConnector)
    assert list(llm.SkillLLMServiceConnector.RETURN_TYPES) == ["LLMServiceConnector"]
