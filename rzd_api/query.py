import logging
import time
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

        headers = {'Accept': 'application/json'}
        if config.user_agent:
            headers['User-Agent'] = config.user_agent
        if config.referer:
            headers['Referer'] = config.referer
        self.session.headers.update(headers)

        if config.proxy:
            self.session.proxies = {
                'http': config.proxy,
                'https': config.proxy,
            }

    def get(self, path: str, params: dict, method: str = 'POST') -> dict | list:
        return self._run(path, params, method)

    def _run(self, path: str, params: dict, method: str) -> dict | list:
        rid = None
        content = None

        for attempt in range(10):
            request_params = dict(params)
            if rid is not None:
                request_params['rid'] = rid

            logger.debug('[attempt %d] %s %s params=%s', attempt + 1, method, path, request_params)

            if method == 'GET':
                response = self.session.get(path, params=request_params, timeout=self.config.timeout)
            else:
                response = self.session.post(path, data=request_params, timeout=self.config.timeout)

            response.raise_for_status()
            content = response.json()

            result = content.get('result', 'OK') if isinstance(content, dict) else 'OK'
            logger.debug('[attempt %d] result=%s', attempt + 1, result)

            if result in ('RID', 'REQUEST_ID'):
                rid = self._get_rid(content)
                time.sleep(1)
            elif result == 'OK':
                try:
                    msg = content['tp'][0]['msgList'][0]['message']
                    raise RzdException(msg)
                except (KeyError, IndexError, TypeError):
                    pass
                return content
            else:
                msg = content.get('message', 'Failed to get request data!') if isinstance(content, dict) else 'Failed to get request data!'
                raise RzdException(msg)

        return content

    def _get_rid(self, content: dict) -> str:
        for key in ('rid', 'RID'):
            if key in content:
                return str(content[key])
        raise RzdException('Rid not found!')
