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


class HttpMethod:
    """HTTP 方法（统一大写，和 requests 约定的写法一致）。

    RequestHandler 靠它判断「参数该放查询串还是请求体」——
    为什么要有这组常量而不是裸写 "GET"：魔法值收口，改规则时只动一处。
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

    # 参数走 URL 查询串的方法；其余走请求体
    QUERY_METHODS = (GET, DELETE)
