from framework.constants.http import Header, HttpMethod, HttpParam
from framework.contracts import CaseLike, ResponseLike, Sender


class RequestHandler:
    """发送请求这一步：把 case 的 method/url/headers/data 交给 HttpClient 发出去。

    **参数位置推断在这个类里做，不在 HttpClient**：
      case.data 是「位置未定」的抽象参数，翻译成 requests 的具体参数位
      （params / json / data）属于适配层的事。HttpClient 是通用底座，只认
      「发什么」，不该知道「为什么这么发」—— 一旦它去判断 Content-Type，
      就认识了业务约定，通用性就没了（决策归适配层，执行归底座）。

    只干「发」这一件事 —— 它不认识 yaml、不做断言。

    ⚠️ 依赖的是 **contracts.Sender 端口**，不是 client.HttpClient 这个具体类 ——
    依赖倒置：内层定契约、外层（HttpClient）实现，conftest 注入。
    换 HTTP 库、甚至换成别的传输方式，这个类一行不用改。

    它由外面注入（不自己 new），所以它的生命周期不归这里管 ——
    谁创建谁销毁，交给 fixture。

    注意别和 client 层的 HttpClient 混了：那个是「HTTP 底座」，这个只是执行流程里发请求的那一步。
    """

    def __init__(self, client: Sender) -> None:
        self.client = client

    def send(self, case: CaseLike) -> ResponseLike:
        return self.client.request(
            method=case.method,
            path=case.url,
            headers=case.headers,
            **self._pick_param_slot(case),
        )

    @staticmethod
    def _pick_param_slot(case: CaseLike) -> dict:
        """把 case.data 翻译成 requests 的参数位置。

        规则（按 HTTP 常识，写用例的人不用操心参数该放哪）：
          - GET / DELETE → 查询串 params
          - POST / PUT   → Content-Type 含 json 就发 json body，否则当表单 data

        暂不支持 files（文件上传）—— 目前没有这类接口，等真有再加分支，
        别为不存在的需求写代码。
        """
        if case.method.upper() in HttpMethod.QUERY_METHODS:
            return {HttpParam.PARAMS: case.data}

        content_type = case.headers.get(Header.CONTENT_TYPE, "")
        if HttpParam.JSON in content_type.lower():
            return {HttpParam.JSON: case.data}

        return {HttpParam.DATA: case.data}
