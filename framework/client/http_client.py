import json
import logging

import requests
from requests import Response
from requests.exceptions import RequestException

from framework.constants.http import Header, HttpParam
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
      - 合并默认 headers、注入 token          -> Context / replacer
      - 断言、提取                            -> Validation / Extract Handler
      - 用例名、测试概念                      -> Runner

    日志一律用 %s 传结构化数据，不用 f-string —— 脱敏 Formatter 要按 key 打码，
    预先渲染成字符串就只剩正则兜底了。
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

        self._log_request(method, url, kwargs)
        try:
            resp = self.session.request(method, url, **kwargs)
        except RequestException as e:
            raise RequestError(f"{method} {url} 请求失败") from e

        logger.info(
            "<-- %s %s %s (%.3fs)",
            resp.status_code,
            method,
            url,
            resp.elapsed.total_seconds(),
        )
        logger.debug("响应体: %s", self._brief_body(resp))

        return resp

    @staticmethod
    def _log_request(method: str, url: str, kwargs: dict) -> None:
        """请求侧日志。INFO 给「发了什么请求」，DEBUG 给具体明细。"""
        logger.info("--> %s %s", method, url)

        if Header.HEADERS in kwargs:
            logger.debug("请求头: %s", kwargs[Header.HEADERS])

        params = {k: v for k, v in kwargs.items() if k in HttpParam.ALL}
        if params:
            logger.debug("请求参数: %s", params)

    @staticmethod
    def _brief_body(resp: Response) -> str:
        """响应体：能当 JSON 解析就缩进打，否则截断 —— 避免一长串挤在一行看不清。"""
        try:
            return json.dumps(resp.json(), ensure_ascii=False, indent=2)
        except ValueError:
            return resp.text[:1000]

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
