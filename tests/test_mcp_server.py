from __future__ import annotations

import json
from typing import Any

import anyio
import httpx
import pytest

from mcp_server import server


async def ok_app(
    scope: dict[str, Any],
    receive: Any,
    send: Any,
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": b'{"ok":true}'})


def request(app: Any, path: str = "/mcp", headers: dict[str, str] | None = None) -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path, headers=headers)

    return anyio.run(run)


def test_bearer_token_middleware_and_health_bypass() -> None:
    app = server.BearerTokenMiddleware(ok_app, "a" * 32)
    assert request(app).status_code == 401
    assert request(app, headers={"Authorization": "Basic abc"}).status_code == 401
    assert request(app, headers={"Authorization": f"Bearer {'b' * 32}"}).status_code == 401
    assert request(app, headers={"Authorization": f"Bearer {'a' * 32}"}).status_code == 200
    assert request(app, path="/health").status_code == 200


def test_rate_limit_and_health_bypass() -> None:
    app = server.RateLimitMiddleware(ok_app, limit_per_minute=1)
    assert request(app).status_code == 200
    response = request(app)
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) >= 1
    assert response.json()["error"] == "rate_limit_exceeded"
    assert request(app, path="/health").status_code == 200
    assert request(server.RateLimitMiddleware(ok_app, 0)).status_code == 200


def test_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    assert server._is_loopback("localhost")
    assert server._is_loopback("127.0.0.1")
    assert not server._is_loopback("0.0.0.0")
    assert not server._is_loopback("example.com")
    assert server._positive_int("10", "VALUE") == 10
    assert server._positive_int("0", "VALUE", allow_zero=True) == 0
    with pytest.raises(ValueError, match="integer"):
        server._positive_int("x", "VALUE")
    with pytest.raises(ValueError, match="between"):
        server._positive_int("0", "VALUE")
    with pytest.raises(ValueError, match="between"):
        server._positive_int("10", "VALUE", maximum=2)

    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "example.com:*, api.example.com")
    assert server._allowed_hosts("0.0.0.0") == ["example.com:*", "api.example.com"]
    monkeypatch.delenv("MCP_ALLOWED_HOSTS")
    assert "example.com:*" in server._allowed_hosts("example.com")


def test_create_mcp_app_exposes_health_and_tools() -> None:
    app = server.create_mcp_app()
    tools = app._tool_manager.list_tools()
    assert {tool.name for tool in tools} == {
        "search_tickets",
        "find_stations",
        "get_carriages",
        "get_train_availability",
        "get_minimal_prices",
        "get_car_scheme",
        "get_car_images",
        "get_route_stations",
    }
    http_app = server.build_http_app(app, token=None, rate_limit=60)
    response = request(http_app, path="/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "rzd-api", "version": "3.0.0"}


class FakeRunApp:
    def __init__(self) -> None:
        self.transport: str | None = None

    def run(self, *, transport: str) -> None:
        self.transport = transport

    def streamable_http_app(self) -> Any:
        return ok_app


def test_main_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FakeRunApp()
    monkeypatch.setattr(server, "create_mcp_app", lambda **_: app)
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    server.main()
    assert app.transport == "stdio"


def test_main_http_runs_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FakeRunApp()
    captured: dict[str, Any] = {}
    monkeypatch.setattr(server, "create_mcp_app", lambda **_: app)
    monkeypatch.setattr(
        "uvicorn.run", lambda application, **kwargs: captured.update(app=application, **kwargs)
    )
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_AUTH_TOKEN", "x" * 32)
    server.main()
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8000
    assert isinstance(captured["app"], server.BearerTokenMiddleware)


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"MCP_TRANSPORT": "sse"}, "MCP_TRANSPORT"),
        ({"MCP_TRANSPORT": "streamable-http", "MCP_HOST": "0.0.0.0"}, "required"),
        (
            {
                "MCP_TRANSPORT": "streamable-http",
                "MCP_HOST": "0.0.0.0",
                "MCP_AUTH_TOKEN": "short",
            },
            "32",
        ),
    ],
)
def test_main_rejects_unsafe_configuration(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for key in ("MCP_TRANSPORT", "MCP_HOST", "MCP_AUTH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(SystemExit) as exc_info:
        server.main()
    assert exc_info.value.code == 2
    assert message in capsys.readouterr().err


def test_json_response_body_is_valid_json() -> None:
    events: list[dict[str, Any]] = []

    async def send(event: dict[str, Any]) -> None:
        events.append(event)

    async def run() -> None:
        await server._json_response(send, 418, {"value": "чай"}, [])

    anyio.run(run)
    assert events[0]["status"] == 418
    assert json.loads(events[1]["body"])["value"] == "чай"
