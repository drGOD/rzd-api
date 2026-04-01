import logging
from typing import Any

import requests
import urllib3

from .config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class RzdException(Exception):
    pass


class Query:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.verify = False

        if config.debug:
            logging.basicConfig(level=logging.DEBUG)
            from http.client import HTTPConnection
            HTTPConnection.debuglevel = 1

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': config.user_agent or (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/146.0.0.0 Safari/537.36'
            ),
            'Referer': config.referer or 'https://ticket.rzd.ru/',
        }
        self.session.headers.update(headers)

        if config.proxy:
            self.session.proxies = {
                'http': config.proxy,
                'https': config.proxy,
            }

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        method: str = 'POST',
        json_body: dict[str, Any] | None = None,
    ) -> dict | list:
        return self._run(path, params or {}, method, json_body)

    def _run(
        self,
        path: str,
        params: dict[str, Any],
        method: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict | list:
        request_params = dict(params)
        logger.debug('%s %s params=%s', method, path, request_params)

        try:
            if method == 'GET':
                response = self.session.get(path, params=request_params, timeout=self.config.timeout)
            else:
                if json_body is not None:
                    response = self.session.post(
                        path,
                        params=request_params,
                        json=json_body,
                        timeout=self.config.timeout,
                    )
                else:
                    response = self.session.post(path, data=request_params, timeout=self.config.timeout)
        except requests.RequestException as exc:
            raise RzdException(f'Request failed: {exc}') from exc

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body_preview = response.text[:300].strip()
            raise RzdException(f'HTTP {response.status_code}: {body_preview}') from exc

        try:
            content = response.json()
        except ValueError as exc:
            body_preview = response.text[:300].strip()
            raise RzdException(f'Unexpected non-JSON response: {body_preview}') from exc

        if isinstance(content, dict):
            error_info = content.get('errorInfo')
            if isinstance(error_info, dict) and error_info.get('Code') not in (None, 0):
                message = error_info.get('Message') or 'RZD API returned an error.'
                raise RzdException(f"RZD API error {error_info.get('Code')}: {message}")

            message = content.get('message')
            if isinstance(message, str) and message:
                raise RzdException(message)

        return content
