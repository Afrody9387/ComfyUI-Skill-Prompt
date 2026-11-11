import asyncio

from aiohttp import web

from .llm_connector import SimpleLLMConnector


async def _connector_action(request, action):
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("请求必须是 JSON 对象。")
        for name in ("base_url", "api_key", "model"):
            if not isinstance(data.get(name, ""), str):
                raise ValueError(f"{name} 必须是文本。")
        timeout = int(data.get("timeout", 120))
        if not 1 <= timeout <= 3600:
            raise ValueError("timeout 必须在 1 到 3600 秒之间。")
        connector = SimpleLLMConnector(data.get("base_url", ""), data.get("api_key", ""), data.get("model", ""), timeout)
        if action == "models":
            models = await asyncio.to_thread(connector.list_models)
            return web.json_response({"ok": True, "models": models})
        result = await asyncio.to_thread(connector.test_connection)
        return web.json_response(result)
    except (ValueError, TypeError) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)


async def get_models(request):
    return await _connector_action(request, "models")


async def test_connection(request):
    return await _connector_action(request, "test")


def register_routes(routes):
    routes.post("/skill-prompt/models")(get_models)
    routes.post("/skill-prompt/test")(test_connection)
