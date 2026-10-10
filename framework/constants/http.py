class HttpParam:
    """requests 里请求体的几种传法。

    HttpClient 打日志时靠它挑拣 —— 只打这些，不把 timeout / verify 之类的噪音也打出来。
    """

    PARAMS = "params"
    DATA = "data"
    JSON = "json"

    ALL = (PARAMS, DATA, JSON)


class Header:
    """常用请求头字段名。"""

    CONTENT_TYPE = "Content-Type"
    HEADERS = "headers"
