import logging

import requests
from requests import Response
from requests.exceptions import RequestException

from framework.exception.errors import RequestError

logger = logging.getLogger(__name__)


class HttpClient:
    """通用 HTTP 底座：只负责「把一次 HTTP 请求发出去」。

    职责（都跟 HTTP 本身有关，跟「测试」无关）：
      - session 复用（保连接 / 保登录态）
      - base_url + path 拼接
      - 统一 timeout
      - 请求 / 响应日志

    不负责（属于别的层，别往这里塞）：
      - 从 yaml / CaseModel 取参数            -> RequestBuilder
      - 合并默认 headers、注入 token          -> RequestBuilder / Context
      - 断言、提取                            -> Validation / Extract Handler
      - 把底层异常转成框架异常                -> 将来的 exception 层
    """

    def __init__(self, base_url: str = "", timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.session()

    def _build_url(self, path: str) -> str:
        # base_url 为空就直接用 path；否则用一个斜杠接起来，避免出现 // 或少 /
        if not self.base_url:
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs) -> Response:
        kwargs.setdefault("timeout", self.timeout)
        url = self._build_url(path)

        logger.info(f"--> {method} {url}")
        try:
            resp = self.session.request(method, url, **kwargs)
        except RequestException as e:
            raise RequestError(f"{method} {url} 请求失败") from e
        logger.info(f"<-- {resp.status_code} {method} {url} ({resp.elapsed.total_seconds():.3f}s)")

        return resp

    def get(self, path: str, **kwargs) -> Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Response:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Response:
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Response:
        return self._request("DELETE", path, **kwargs)

    def close(self) -> None:
        self.session.close()
