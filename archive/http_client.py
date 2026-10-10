import logging

import requests


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
class HttpClient:

    def __init__(self, base_url="",timeout=10,use_session=True):
        self.base_url = base_url
        self.timeout = timeout
        if use_session: self.session = requests.session()

    def _request(self, method, path, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        logger.info(f'method: {method}, url: {self.base_url+path}')
        return self.session.request(method, self.base_url + path, **kwargs)

    def get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self._request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self._request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self._request("DELETE", path, **kwargs)

    def close(self):
        self.session.close()