from __future__ import annotations

from typing import Any

import pytest
import requests

from rzd_api.config import Config
from rzd_api.exceptions import RzdAPIError, RzdHTTPError, RzdTransportError
from rzd_api.query import RzdTransport


class FakeResponse:
    def __init__(
        self,
        payload: Any = None,
        *,
        status_code: int = 200,
        text: str = "",
        json_error: bool = False,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = text
        self.json_error = json_error

    def json(self) -> Any:
        if self.json_error:
            raise ValueError("bad json")
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.verify = True
        self.headers: dict[str, str] = {}
        self.proxies: dict[str, str] = {}
        self.adapters: dict[str, Any] = {}
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def mount(self, prefix: str, adapter: Any) -> None:
        self.adapters[prefix] = adapter

    def request(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def close(self) -> None:
        self.closed = True


def make_transport(
    response: FakeResponse | Exception, **config: Any
) -> tuple[RzdTransport, FakeSession]:
    session = FakeSession(response)
    transport = RzdTransport(Config(**config), session=session)  # type: ignore[arg-type]
    return transport, session


def test_transport_configures_session_and_request() -> None:
    transport, session = make_transport(
        FakeResponse({"ok": True}),
        proxy="http://proxy.invalid",
        user_agent="test-agent",
        referer="https://example.test/",
        connect_timeout=2,
        read_timeout=7,
    )
    result = transport.request_json(
        "get", "https://example.test/path", params={"a": 1}, json_body={"b": 2}
    )
    assert result == {"ok": True}
    assert session.verify is False
    assert session.headers["User-Agent"] == "test-agent"
    assert session.proxies["https"] == "http://proxy.invalid"
    assert set(session.adapters) == {"http://", "https://"}
    assert session.calls[0]["timeout"] == (2, 7)
    assert session.calls[0]["method"] == "GET"
    retry = session.adapters["https://"].max_retries
    assert retry.total == 3
    assert retry.backoff_factor == 0.5
    assert retry.respect_retry_after_header is True
    assert retry.allowed_methods == frozenset({"GET", "POST"})
    assert retry.status_forcelist == (429, 500, 502, 503, 504)


def test_transport_rejects_method_and_closed_client() -> None:
    transport, _ = make_transport(FakeResponse({}))
    with pytest.raises(ValueError, match="Unsupported"):
        transport.request_json("DELETE", "https://example.test")
    transport.close()
    with pytest.raises(RzdTransportError, match="closed"):
        transport.request_json("GET", "https://example.test")


def test_owned_session_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(FakeResponse({}))
    monkeypatch.setattr(requests, "Session", lambda: session)
    with RzdTransport(Config()) as transport:
        assert transport.session is session
    assert session.closed is True
    transport.close()


def test_injected_session_is_not_closed() -> None:
    transport, session = make_transport(FakeResponse({}))
    transport.close()
    assert session.closed is False


def test_request_exception_becomes_transport_error() -> None:
    transport, _ = make_transport(requests.ConnectionError("offline"))
    with pytest.raises(RzdTransportError, match="offline"):
        transport.request_json("GET", "https://example.test")


def test_http_non_json_and_scalar_errors() -> None:
    transport, _ = make_transport(FakeResponse({}, status_code=503, text="unavailable"))
    with pytest.raises(RzdHTTPError) as exc_info:
        transport.request_json("GET", "https://example.test")
    assert exc_info.value.status_code == 503
    assert exc_info.value.body_preview == "unavailable"

    transport, _ = make_transport(FakeResponse(text="html", json_error=True))
    with pytest.raises(RzdTransportError, match="non-JSON"):
        transport.request_json("GET", "https://example.test")

    transport, _ = make_transport(FakeResponse("scalar"))
    with pytest.raises(RzdTransportError, match="scalar"):
        transport.request_json("GET", "https://example.test")


def test_api_error_shapes() -> None:
    transport, _ = make_transport(
        FakeResponse({"errorInfo": {"Code": 42, "Message": "bad request"}})
    )
    with pytest.raises(RzdAPIError) as exc_info:
        transport.request_json("GET", "https://example.test")
    assert exc_info.value.code == 42
    assert exc_info.value.message == "bad request"

    transport, _ = make_transport(FakeResponse({"message": "maintenance"}))
    with pytest.raises(RzdAPIError, match="maintenance"):
        transport.request_json("GET", "https://example.test")

    for code in (0, "0", None):
        transport, _ = make_transport(FakeResponse({"errorInfo": {"Code": code}}))
        assert transport.request_json("GET", "https://example.test") == {
            "errorInfo": {"Code": code}
        }
