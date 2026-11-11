"""A direct OpenAI-compatible connector, with no key-file overrides."""
import copy
import hashlib
import json
import re
import time
from urllib.parse import urlsplit, urlunsplit

import requests
from comfy_api.latest import io


def api_endpoints(base_url):
    url = urlsplit(base_url.strip())
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise ValueError("请填写 http:// 或 https:// 开头的 API 地址。")
    if url.query or url.fragment:
        raise ValueError("API 地址不要带查询参数或 #；密钥请填在 api_key 中。")
    path = url.path.rstrip("/")
    for suffix in ("/chat/completions", "/models"):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    else:
        if not path:
            path = "/v1"
    base = urlunsplit((url.scheme, url.netloc, path, "", ""))
    return base + "/chat/completions", base + "/models"


class SimpleLLMConnector:
    def __init__(self, base_url, api_key, model, timeout=120):
        self.api_url, self.models_url = api_endpoints(base_url)
        self.api_token = api_key.strip()
        if self.api_token.lower().startswith("bearer "):
            self.api_token = self.api_token[7:].strip()
        self.model = model.strip()
        self.timeout = timeout

    def get_state(self):
        state = (self.api_url, self.api_token, self.model, self.timeout)
        return hashlib.sha256(json.dumps(state).encode("utf-8")).hexdigest()

    def _redact(self, text):
        return str(text).replace(self.api_token, "[redacted]") if self.api_token else str(text)

    def _request(self, method, url, payload=None):
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = "Bearer " + self.api_token
        try:
            response = requests.request(method, url, headers=headers, json=payload, timeout=self.timeout)
        except requests.Timeout:
            raise ValueError(f"连接超时（{self.timeout} 秒）；请检查地址、网络或增加 timeout。") from None
        except requests.RequestException as exc:
            raise ValueError("连接失败：" + self._redact(exc)) from None
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            raise ValueError(f"HTTP {response.status_code}：服务未返回 JSON，请确认填的是 API 地址。") from None
        return response.status_code, data

    def _error(self, status, data):
        error = data.get("error", data) if isinstance(data, dict) else data
        detail = error.get("message", error) if isinstance(error, dict) else error
        hints = {
            401: "密钥无效或缺失", 403: "密钥没有权限", 404: "接口地址或模型不存在",
            429: "请求限流或额度不足",
        }
        hint = hints.get(status, "服务请求失败")
        return ValueError(f"HTTP {status}（{hint}）：{self._redact(detail)[:800]}")

    def list_models(self):
        status, data = self._request("GET", self.models_url)
        if status != 200:
            raise self._error(status, data)
        entries = data.get("data") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise ValueError("模型列表格式不兼容：需要 /models 返回 data 数组；仍可手动填写模型 ID。")
        models = sorted({item["id"] for item in entries
                         if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()})
        if not models:
            raise ValueError("服务返回了空模型列表；仍可手动填写模型 ID。")
        return models

    def _complete(self, messages, **kwargs):
        if not self.model:
            raise ValueError("请先填写 model，或点击“获取模型”选择一个。")
        messages = copy.deepcopy(messages)
        for message in messages:
            if isinstance(message.get("content"), list):
                for part in message["content"]:
                    image = part.get("image_url")
                    if isinstance(image, dict) and image.get("detail") == "auto":
                        del image["detail"]
        payload = {"model": self.model, "messages": messages, "stream": False}
        for name in ("max_tokens", "temperature", "top_p", "seed"):
            if kwargs.get(name) is not None:
                payload[name] = kwargs[name]
        while True:
            status, data = self._request("POST", self.api_url, payload)
            if status == 200:
                break
            # Only retry an explicit parameter rejection; no retry of completed generations or network failures.
            error = data.get("error", {}) if isinstance(data, dict) else {}
            detail = str(error.get("message", "")).lower() if isinstance(error, dict) else str(error).lower()
            parameter = error.get("param") if isinstance(error, dict) else None
            rejected = status in (400, 422) and any(word in detail for word in (
                "unsupported", "not supported", "not support", "unknown", "unrecognized", "not permitted",
            ))
            if rejected:
                candidates = [name for name in ("seed", "temperature", "top_p", "max_tokens", "max_completion_tokens")
                              if name in payload and (parameter == name or re.search(rf"\b{name}\b", detail))]
                if candidates:
                    name = candidates[0]
                    if name == "max_tokens" and "max_completion_tokens" in detail:
                        payload["max_completion_tokens"] = payload.pop(name)
                    else:
                        del payload[name]
                    continue
            raise self._error(status, data)
        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ValueError("服务响应格式不兼容：缺少 choices[0].message.content。") from None
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if not isinstance(content, str):
            raise ValueError("服务未返回文本内容。")
        content = re.sub(r"<(think|thinking)>[\s\S]*?</\1>", "", content, flags=re.IGNORECASE).strip()
        return content, choice.get("finish_reason", "unknown")

    def invoke(self, messages, **kwargs):
        content, finish = self._complete(messages, **kwargs)
        if not content:
            raise ValueError(f"服务返回空正文（finish_reason={finish}）；若为 length，请提高生成节点的 max_tokens。")
        return content

    def test_connection(self):
        started = time.perf_counter()
        reply, finish = self._complete([{"role": "user", "content": "Reply with OK only."}], max_tokens=64)
        if not reply:
            reply = f"API 已响应，但测试未返回正文（finish_reason={finish}）；推理模型可能用尽了短测试的输出额度。"
        return {"ok": True, "model": self.model, "elapsed_seconds": round(time.perf_counter() - started, 2),
                "reply": self._redact(reply)[:300]}


class SkillLLMServiceConnector(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SkillLLMServiceConnector",
            display_name="Simple LLM Connector · 简洁 LLM 连接器",
            category="Skill Prompt",
            description="直接填写地址、密钥、模型；支持 OpenAI 兼容服务，可获取模型和测试连接。",
            inputs=[
                io.String.Input("base_url", default="", dynamic_prompts=False,
                                tooltip="API 基础地址（如 https://api.venice.ai/api/v1），也接受完整 /chat/completions 地址。"),
                io.String.Input("api_key", default="", dynamic_prompts=False,
                                tooltip="直接使用此密钥，不读取配置文件。本地免密服务可留空；此值会随工作流保存。"),
                io.String.Input("model", default="", dynamic_prompts=False,
                                tooltip="服务商模型 ID，可手填，也可点击“获取模型”选择。"),
                io.Int.Input("timeout", default=120, min=1, max=3600, optional=True,
                             tooltip="单次请求超时秒数。测试连接会实际发送一条很短的生成请求。"),
            ],
            outputs=[io.Custom("LLMServiceConnector").Output(display_name="llm_service_connector")],
        )

    @classmethod
    def execute(cls, base_url, api_key, model, timeout=120):
        return io.NodeOutput(SimpleLLMConnector(base_url, api_key, model, timeout))
