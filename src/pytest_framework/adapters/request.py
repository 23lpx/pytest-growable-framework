from urllib.parse import quote

from pytest_framework.entities.constants.http import Header, HttpMethod, HttpParam
from pytest_framework.entities.contracts import CaseLike, ResponseLike
from pytest_framework.entities.exception.errors import RequestError
from pytest_framework.ports.sender import Sender


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
            path=self._build_path(case),
            headers=case.headers,
            **self._pick_param_slot(case),
        )

    @staticmethod
    def _build_path(case: CaseLike) -> str:
        """把路径参数填进 url 的 `{占位符}`。

        yaml 里 url 写 `/api/group/v1/detail/{groupId}`，用例给
        `path_params: {groupId: 123}` → 拼出 `/api/group/v1/detail/123`。

        **为什么不复用 `${}` 那套变量池**：变量池是 session 级共享的，而路径参数
        几乎每条用例都不同（查自己的分组 / 查不存在的 id / 查别人的），塞进共享池
        会互相污染 —— 前一条写进去的值后一条还在。`path_params` 是「这一条用例
        自己的」，作用域正好。它内部**仍可用 `${}`**（由 replacer 先解析），
        所以两种机制是叠加的，不是二选一：`{groupId}: "${group_id}"` 也成立。

        值做 URL 编码：路径参数可能是 `-1`、`abc`，也可能是注入串
        （`' OR '1'='1`），直接拼进 url 会破坏路径结构。
        """
        path = case.url
        for name, value in case.path_params.items():
            path = path.replace("{" + name + "}", quote(str(value), safe=""))

        # 填完还有 {xxx} 说明用例漏给了参数 —— 早点喊，别让它带着一个不可能
        # 匹配的 url 发出去（那种失败只会得到个 404，看不出是数据没填）
        if "{" in path:
            raise RequestError(f"路径参数没填全，url 里仍残留占位符: {path}")

        return path

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
