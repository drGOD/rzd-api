from __future__ import annotations

import logging
import time
from typing import Any

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Config
from .exceptions import RzdAPIError, RzdHTTPError, RzdTransportError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

JsonPayload = dict[str, Any] | list[Any]


class RzdTransport:
    """Internal HTTP transport with bounded retries and structured errors."""

    def __init__(self, config: Config, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()
        self._owns_session = session is None
        self._closed = False

        # Kept unchanged for 2.0 by explicit project decision.
        self.session.verify = False
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": config.user_agent
                or (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/146.0.0.0 Safari/537.36"
                ),
                "Referer": config.referer or "https://ticket.rzd.ru/",
            }
        )

        if config.proxy:
            self.session.proxies.update({"http": config.proxy, "https": config.proxy})

        retry = Retry(
            total=config.retry_total,
            connect=config.retry_total,
            read=config.retry_total,
            status=config.retry_total,
            allowed_methods=frozenset({"GET", "POST"}),
            status_forcelist=(429, 500, 502, 503, 504),
            backoff_factor=config.retry_backoff,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> JsonPayload:
        if self._closed:
            raise RzdTransportError("The RZD client is closed.")

        normalized_method = method.upper()
        if normalized_method not in {"GET", "POST"}:
            raise ValueError(f"Unsupported HTTP method: {method}")

        started_at = time.monotonic()
        logger.debug("RZD request started: %s %s", normalized_method, url)
        try:
            response = self.session.request(
                method=normalized_method,
                url=url,
                params=params,
                json=json_body,
                timeout=(self.config.connect_timeout, self.config.read_timeout),
            )
        except requests.RequestException as exc:
            raise RzdTransportError(f"RZD request failed: {exc}") from exc
        finally:
            logger.debug(
                "RZD request finished: %s %s elapsed=%.3fs",
                normalized_method,
                url,
                time.monotonic() - started_at,
            )

        if not 200 <= response.status_code < 300:
            raise RzdHTTPError(response.status_code, response.text[:300].strip())

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise RzdTransportError(
                f"RZD returned non-JSON content: {response.text[:300].strip()}"
            ) from exc

        if not isinstance(payload, (dict, list)):
            raise RzdTransportError("RZD returned a JSON scalar instead of an object or array.")

        if isinstance(payload, dict):
            self._raise_api_error(payload)
        return payload

    @staticmethod
    def _raise_api_error(payload: dict[str, Any]) -> None:
        error_info = payload.get("errorInfo")
        if isinstance(error_info, dict) and str(error_info.get("Code") or "0") != "0":
            raise RzdAPIError(
                error_info.get("Code"),
                str(error_info.get("Message") or "RZD API returned an error."),
            )

        message = payload.get("message")
        if isinstance(message, str) and message:
            raise RzdAPIError(message=message)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> RzdTransport:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
