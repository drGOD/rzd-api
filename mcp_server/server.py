from __future__ import annotations

import hashlib
import ipaddress
import math
import os
import secrets
import sys
import threading
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from rzd_api import RoundTripResult, RzdClient


def search_tickets(
    from_station: str,
    to_station: str,
    departure_date: str,
    return_date: str | None = None,
    adults: int = 1,
    children: int = 0,
    only_with_seats: bool = True,
    include_transfers: bool = False,
    transport_type: str = "all",
) -> dict[str, Any] | list[dict[str, Any]]:
    """Search direct RZD routes by station name/code and departure date."""
    with RzdClient() as client:
        result = client.search_tickets(
            from_station,
            to_station,
            departure_date,
            return_date,
            adults=adults,
            children=children,
            only_with_seats=only_with_seats,
            include_transfers=include_transfers,
            transport_type=transport_type,
        )
        if isinstance(result, RoundTripResult):
            return result.to_dict()
        return [route.to_dict() for route in result]


def find_stations(
    query: str,
    transport_type: str = "rail,suburban",
    group_results: bool = True,
) -> list[dict[str, Any]]:
    """Find station candidates, including synonym matches."""
    with RzdClient() as client:
        return [
            station.to_dict()
            for station in client.find_stations(
                query,
                transport_type=transport_type,
                group_results=group_results,
            )
        ]


def get_carriages(
    from_station: str,
    to_station: str,
    departure_date: str,
    departure_time: str,
    train_number: str,
    provider: str = "P1",
) -> dict[str, Any]:
    """Get typed carriage and seat availability details for a train."""
    with RzdClient() as client:
        return client.get_carriages(
            from_station,
            to_station,
            departure_date,
            departure_time,
            train_number,
            provider=provider,
        ).to_dict()


def get_train_availability(
    from_station: str,
    to_station: str,
    date_from: str,
    date_to: str,
) -> dict[str, Any]:
    """Get dates with available trains for a direction."""
    with RzdClient() as client:
        return client.get_train_availability(from_station, to_station, date_from, date_to).to_dict()


def get_minimal_prices(
    from_station: str,
    to_station: str,
    date_from: str,
) -> dict[str, Any]:
    """Get the minimum published prices from a selected date."""
    with RzdClient() as client:
        return client.get_minimal_prices(from_station, to_station, date_from).to_dict()


def get_car_scheme(
    departure_date: str,
    departure_time: str,
    train_number: str,
    car_number: str,
    car_sub_type: str,
    service_class: str,
    carrier: str,
    car_numeration: str = "FromHead",
) -> dict[str, Any]:
    """Get carriage scheme metadata."""
    with RzdClient() as client:
        return client.get_car_scheme(
            departure_date,
            departure_time,
            train_number,
            car_number,
            car_sub_type,
            service_class,
            carrier,
            car_numeration=car_numeration,
        ).to_dict()


def get_car_images(
    departure_date: str,
    departure_time: str,
    train_number: str,
    car_number: str,
    car_sub_type: str,
    service_class: str,
    carrier: str,
    car_numeration: str = "FromHead",
) -> dict[str, Any]:
    """Get carriage image metadata."""
    with RzdClient() as client:
        return client.get_car_images(
            departure_date,
            departure_time,
            train_number,
            car_number,
            car_sub_type,
            service_class,
            carrier,
            car_numeration=car_numeration,
        ).to_dict()


def get_route_stations(
    from_station: str,
    to_station: str,
    departure_date: str,
    departure_time: str,
    train_number: str,
    provider: str = "P1",
) -> dict[str, Any]:
    """Get all stations for a train and direction."""
    with RzdClient() as client:
        return client.get_route_stations(
            from_station,
            to_station,
            departure_date,
            departure_time,
            train_number,
            provider=provider,
        ).to_dict()


def create_mcp_app(*, host: str = "127.0.0.1", port: int = 8000) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.server.fastmcp.server import TransportSecuritySettings
        from starlette.requests import Request
        from starlette.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "MCP support is not installed. Install it with: pip install 'rzd-api[mcp]'"
        ) from exc

    allowed_hosts = _allowed_hosts(host)
    app = FastMCP(
        "RZD API",
        host=host,
        port=port,
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=[f"http://{value}" for value in allowed_hosts],
        ),
    )
    app.tool()(search_tickets)
    app.tool()(find_stations)
    app.tool()(get_carriages)
    app.tool()(get_train_availability)
    app.tool()(get_minimal_prices)
    app.tool()(get_car_scheme)
    app.tool()(get_car_images)
    app.tool()(get_route_stations)

    @app.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "rzd-api", "version": "3.0.0"})

    return app


class BearerTokenMiddleware:
    """Small ASGI bearer-token guard for MCP endpoints."""

    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http" or scope.get("path") == "/health":
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        authorization = headers.get("authorization", "")
        scheme, _, candidate = authorization.partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(candidate, self.token):
            await _json_response(
                send,
                401,
                {"error": "unauthorized"},
                [(b"www-authenticate", b"Bearer")],
            )
            return
        await self.app(scope, receive, send)


class RateLimitMiddleware:
    """In-memory sliding-window limiter keyed by token digest or client IP."""

    def __init__(self, app: Any, limit_per_minute: int = 60) -> None:
        self.app = app
        self.limit = limit_per_minute
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if self.limit == 0 or scope.get("type") != "http" or scope.get("path") == "/health":
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        key = self._key(scope)
        retry_after = 0
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and now - timestamps[0] >= 60:
                timestamps.popleft()
            if len(timestamps) >= self.limit:
                retry_after = max(1, math.ceil(60 - (now - timestamps[0])))
            else:
                timestamps.append(now)

        if retry_after:
            await _json_response(
                send,
                429,
                {"error": "rate_limit_exceeded", "retry_after": retry_after},
                [(b"retry-after", str(retry_after).encode("ascii"))],
            )
            return
        await self.app(scope, receive, send)

    @staticmethod
    def _key(scope: dict[str, Any]) -> str:
        authorization = _headers(scope).get("authorization", "")
        if authorization:
            return "token:" + hashlib.sha256(authorization.encode()).hexdigest()
        client = scope.get("client")
        return f"ip:{client[0] if client else 'unknown'}"


def build_http_app(app: Any, *, token: str | None, rate_limit: int) -> Any:
    asgi_app: Any = app.streamable_http_app()
    asgi_app = RateLimitMiddleware(asgi_app, rate_limit)
    if token:
        asgi_app = BearerTokenMiddleware(asgi_app, token)
    return asgi_app


def main() -> None:
    try:
        transport = os.getenv("MCP_TRANSPORT", "stdio")
        if transport not in {"stdio", "streamable-http"}:
            raise ValueError("MCP_TRANSPORT must be 'stdio' or 'streamable-http'.")

        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = _positive_int(os.getenv("MCP_PORT", "8000"), "MCP_PORT", maximum=65535)
        rate_limit = _positive_int(
            os.getenv("MCP_RATE_LIMIT_PER_MINUTE", "60"),
            "MCP_RATE_LIMIT_PER_MINUTE",
            allow_zero=True,
        )
        token = os.getenv("MCP_AUTH_TOKEN") or None

        if transport == "streamable-http":
            if token and len(token) < 32:
                raise ValueError("MCP_AUTH_TOKEN must contain at least 32 characters.")
            if not _is_loopback(host) and not token:
                raise ValueError("MCP_AUTH_TOKEN is required when MCP_HOST is not loopback.")

        app = create_mcp_app(host=host, port=port)
        if transport == "stdio":
            app.run(transport="stdio")
            return

        import uvicorn

        uvicorn.run(
            build_http_app(app, token=token, rate_limit=rate_limit),
            host=host,
            port=port,
            log_level=os.getenv("MCP_LOG_LEVEL", "info").lower(),
        )
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


def _allowed_hosts(host: str) -> list[str]:
    configured = os.getenv("MCP_ALLOWED_HOSTS")
    if configured:
        return [item.strip() for item in configured.split(",") if item.strip()]
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    if host not in {"0.0.0.0", "::"} and not _is_loopback(host):
        hosts.append(f"{host}:*")
    return hosts


def _is_loopback(host: str) -> bool:
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _positive_int(
    value: str,
    name: str,
    *,
    maximum: int | None = None,
    allow_zero: bool = False,
) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    minimum = 0 if allow_zero else 1
    if parsed < minimum or (maximum is not None and parsed > maximum):
        raise ValueError(f"{name} must be between {minimum} and {maximum or 'unbounded'}.")
    return parsed


def _headers(scope: dict[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


async def _json_response(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    status: int,
    body: dict[str, Any],
    extra_headers: list[tuple[bytes, bytes]],
) -> None:
    import json

    content = json.dumps(body).encode("utf-8")
    headers = [(b"content-type", b"application/json"), *extra_headers]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": content})


if __name__ == "__main__":
    main()
