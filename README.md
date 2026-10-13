# 接口自动化（pytest + 自研框架）

用 pytest 做执行底座，自研一套**分层的数据驱动**接口测试框架，跑商用短链平台的接口用例。
框架单测走 **GitHub Actions**，接口用例走 **Jenkins**。

---

## 快速开始

环境：Python 3.12，venv 在 `.venv/`。

```bash
# 1) 装依赖 —— 依赖的唯一来源是 pyproject.toml，这一步同时把包可编辑安装（指向 src/）
./.venv/Scripts/python.exe -m pip install -r requirements.txt

# 2) 备一份环境配置（config/config.yaml 不入库，从模板拷）
cp config/config.example.yaml config/config.yaml     # 再填：被测地址 / 测试账号 / 本地工作库密码

# 3) 跑接口用例（testpaths = cases）
./.venv/Scripts/python.exe -m pytest
```

> ⚠️ 一律用 `./.venv/Scripts/python.exe -m ...`，别直接敲 `pip` / `activate` —— venv 的绝对路径写死在 `pyvenv.cfg` / `activate` / `pip.exe` 里。

---

## 被测系统

**商用短链平台**（Java / Spring Cloud，多模块），经网关接。地址配在 `config/config.yaml` 的 `shortlink.base_url`。

| 项 | 说明 |
|---|---|
| 鉴权 | 登录接口免登，返回的 token 放**请求头**（`token: <JWT>`）；缺 / 错 token → `code=250004` |
| 成功判据 | **`code=0`** —— 业务失败**也是 HTTP 200**，只看响应体的 `code`（`contains` 是**精确等值**，不是子串） |
| 账号 | 测试账号配在 `config/config.yaml` 的 `shortlink` 段（**不入库**），用例用 `${shortlink.phone}` / `${shortlink.pwd}` 引用，**不写死** |
| 接口 | `/account-server/*`（账号）、`/link-server/api/group/*`（分组）、`/link-server/api/link/*`（短链）、`/link-server/api/domain/*`（域名） |

⚠️ **服务器按需开关**（测试应用机 + 中间件机），连不上先确认那两台机器开着。

> **历史**：研发期用过 `flaskServer.exe`（本地 PyQt5 mock）练手，2026-10-12 已归档到 `archive/`。
> 它是**纯内存 mock、没有数据库**，所以「查库校验」那一步它教不了。需要看当年怎么写的就看 `archive/`，别拿来跑。

---

## 项目结构

自研框架，**src-layout + 按架构层分目录**（目录名自己就说明了分层）：

```
src/pytest_framework/
├── entities/         ← 最内：零第三方依赖；模型 / 变量池 / 契约 / 异常 / 常量
├── ports/            ← 端口：内层定契约、外层实现（sender / query）
├── usecases/         ← 编排：case_runner / scenario_runner
├── adapters/         ← 适配：request / validation / db_checker / extract / execute_case / reader / config
└── infrastructure/   ← 最外：http(requests) / logging / report(allure) / path / db(pymysql)
        ↑ 依赖方向一路向内：infrastructure → adapters → usecases → ports → entities
```

**数据流**（两条路径最终汇合到同一个执行器）：

```
data/api_shortlink/*.yaml  ← 单接口（dict：base_info + test_cases）
data/scenarios/*.yaml      ← 场景（list：N 个接口块，**顺序即执行顺序**）
   │
   ├─ 单接口 ── CaseModel.discover() 扫目录
   │     │  adapters/reader.YamlRead.read
   │     ▼
   │   entities/CaseModel         封装：dict → 统一模型 {api, cases[]}
   │     │
   │     ▼
   │   adapters/ExecuteCase       适配：模型 → 执行器契约（一条 = 一个执行单元）
   │     │  ExecuteCase.discover() **展平**
   │     ▼
   │   pytest 参数化               ← 多 case 调度权在 pytest 手里
   │     每条 case 一个节点（保住 -k / -m / 重跑 / -n 的粒度）
   │
   └─ 场景 ── ScenarioModel.discover() 扫目录（**不展平**）
         │  adapters/reader.YamlRead.read
         ▼
       entities/ScenarioModel      = list[CaseModel]，**复用**单接口解析器（只是拼积木）
         │
         ▼
       usecases/ScenarioRunner     顺序编排 + 步骤日志（整个场景 = 一个节点）
         │
         └────────────┐
                      ▼
        usecases/CaseRunner.run(case)   ← 两条路径在此汇合，只跑「一条」
          ├── entities/context/replacer.resolve_case  解析 ${...} → 产出副本（不改原 case）
          ├── adapters/RequestHandler   依赖 ports/Sender ← infrastructure/HttpClient
          ├── adapters/ValidationHandler  校验**响应**（fail-fast：不过就不写变量池）
          ├── adapters/DbChecker         校验**库**（yaml 的 db 段；没写就跳过）
          └── adapters/ExtractHandler     提取 → entities/Context（供后续用例引用）
```

**怎么找到包**：两次保险 —— `pytest.ini` 的 `pythonpath = src`（clone 下来直接跑）+ `pyproject.toml`（`pip install -e .` 后任何地方都能 import）。

**数据驱动（两种发现，同一个模式）**：

| | 发现 | 展平？ | 结果粒度 | 用在 |
|---|---|---|---|---|
| 单接口 | `CaseModel.discover()` → `ExecuteCase.discover()` | ✅ 展平 | **一条 case 一个节点** | 数据驱动**主力**（量大、独立） |
| 场景 | `ScenarioModel.discover()` | ❌ 不展平 | **一个场景一个节点** | 有**先后关系**的流程（分组生命周期、重名判重） |

**加数据文件 = 加用例，代码一个字不改** —— `cases/test_shortlink.py` 把 `data/api_shortlink/` 下的用例**展平**成 pytest 节点，`cases/test_scenario.py` 把 `data/scenarios/` 的每条场景收成**一个**节点。粒度差别就在「要不要展平」这一处。

**两条路径，一个执行器**：两者最终都调 `CaseRunner.run(case)` —— **它永远只跑一条**，不认识"列表"、也不认识"场景"。循环策略归调用方，执行能力归 `CaseRunner`。

| 层 | 文件 | 职责 |
|---|---|---|
| **entities** | `entities/model/` | 用例模型（`CaseModel` / `ScenarioModel`）+ `discover()` 扫目录 |
| | `entities/context/` | 变量池 / 占位符解析 / 函数市场 |
| | `entities/contracts.py` | 契约：`CaseLike` / `ResponseLike` / `VariableSource` |
| | `entities/exception/` | 异常体系 |
| | `entities/constants/` | 常量（魔法值收口） |
| **ports** | `ports/sender.py` | `Sender` —— 发请求的端口，`HttpClient` 实现 |
| | `ports/query.py` | `QueryExecutor` —— 打 SQL 拿回行的端口（**只读**），`infrastructure/db.py` 实现 |
| **usecases** | `usecases/case_runner.py` | 编排单条用例（不认识"列表/场景"） |
| | `usecases/scenario_runner.py` | 场景编排（顺序 + 步骤日志，内部调 `CaseRunner`） |
| **adapters** | `adapters/execute_case.py` | 适配（模型 → 执行单元）+ `discover()` 展平。**不 import pytest** |
| | `adapters/request.py` | 发送请求（依赖 `Sender` 端口，**不 import requests / HttpClient**） |
| | `adapters/validation.py` | 校验响应 |
| | `adapters/db_checker.py` | 校验库（声明式期望 → SQL → 比对，**yaml 里不写 SQL**） |
| | `adapters/extract.py` | 提取（jsonpath → 变量池） |
| | `adapters/reader.py` | 读 yaml → dict |
| | `adapters/config.py` | 配置加载（yaml + 环境变量覆盖），可当 `Context` 的父级 |
| **infra** | `infrastructure/http.py` | HTTP 底座（**不认识测试概念**） |
| | `infrastructure/logging/` | 日志（**含脱敏**） |
| | `infrastructure/report.py` | allure 薄封装（框架唯一认识 allure 的地方） |
| | `infrastructure/path.py` | `_project_root()` |
| | `infrastructure/db.py` | MySQL 底座（pymysql / DictCursor / 断线重连）。**不认识测试概念** |

**资源生命周期靠依赖注入**：`HttpClient` 由 `conftest` 的 `client` fixture（**session 级**，为连接复用）创建并 `close()`；`Context`（变量池）由 `context` fixture（**session 级**，跨用例关联必须共享）提供。`CaseRunner` / `RequestHandler` **只收不 new**。整轮测试共用 1 条连接。

**依赖倒置：内层只认端口，不认实现** —— `adapters` / `usecases` 依赖 `ports.Sender` / `ports.QueryExecutor`（端口）+ `entities.contracts.ResponseLike`（响应契约），**不 import `infrastructure.HttpClient`、也不 import `requests`**；`adapters` **不 import pytest**。全仓**只有 `conftest` 知道 `HttpClient` 存在**。判据：**内层模块的 import 里有没有出现具体库或外层类**。

**配置当变量池的父级**：`context` fixture 建的是 `Context(parent=config)` —— `${...}` 因此只有**一个入口**：`${token}` 查变量层（运行时提取的），`${shortlink.phone}` 落到配置层。**配置层只读**：用例 `set` 同名 key 只写自己那层，覆盖不了配置。`Context` 只认 `VariableSource` 契约，**不认识 `Config`**。

**占位符替换必须产副本**：`resolve_case()` 返回 `ResolvedCase`，**绝不就地改原 case** —— `ExecuteCase` 是收集阶段构造、整个 session 共用的（含 `--reruns`），就地改会让第二遍跑到脏数据。

**跨用例关联靠 fixture，不靠执行顺序**：pytest 按**文件名字典序**收集，"登录先跑"天然不成立。要前置数据就声明 `conftest` 的 fixture —— `shortlink_login`（登一次写 token）、`shortlink_prepare`（造只读的公共前置），`cases/test_shortlink.py` 把它们挂给了所有用例（session 级只跑一次，零成本）。

### 目录

| 目录 / 文件 | 干什么 |
|---|---|
| `cases/` | 测试入口，三个文件：`test_shortlink.py`（单接口，数据驱动）/ `test_scenario.py`（场景）/ `test_shortlink_flow.py`（逃生舱 —— 流程里有轮询等待的）。**加数据文件 = 加用例** |
| `src/pytest_framework/` | **框架本体**，按架构层分目录 |
| `tests/` | **框架自身的单测**（不依赖被测服务）。不在 `testpaths` 里，要显式 `pytest tests/` |
| `data/api_shortlink/` | **单接口**数据 yaml（一个接口一个文件，`base_info` + `test_cases`）。**加文件 = 加用例** |
| `data/scenarios/` | **业务场景** yaml（根节点是列表，N 个接口块按顺序）。有先后关系的流程放这儿 |
| `config/` | **环境配置**：`config.yaml`（**不入库**，在 `.gitignore` 里）+ `config.example.yaml`（占位符模板）。换环境改这份，用例不用动 |
| `archive/` | **归档区**：不再维护、pytest 也收不到（`testpaths = cases`）。现在装的是 flaskServer 那套 |
| `docs/` | 设计文档：代码规范 / 架构审查 / 设计说明 |
| `conftest.py` | **Composition Root** —— 唯一 `new` 具体实现的地方：各类 fixture + `init_logger()` |
| `pytest.ini` / `pyproject.toml` | pytest 配置（含 `pythonpath = src`）/ 打包声明 + 依赖清单 |
| `logs/` `reports/` | 日志（按天切，**已脱敏**）/ 报告产物，**不进 git** |
| `tools/` | 本地工具（allure 命令行），**不进 git**。各人自己解压一份 |
| `scripts/` | CI 胶水（`notify.py`）+ 兜底清理（`clean_testdata.py`） |

---

## 用例怎么写

### 单接口（数据驱动主力）

一个接口一个 yaml：根节点是 **dict**（`base_info` + `test_cases`），一条 case 一个 pytest 节点。

```yaml
# data/api_shortlink/group_post_group_add.yaml（节选）
base_info:
  api_name: group-add
  url: '/link-server/api/group/v1/add'
  method: POST
  headers:
    'Content-Type': 'application/json'

test_cases:
  - case_name: "创建分组：正常创建（基准）"
    headers:
      token: "${token}"
    data:
      title: "g1_auto_${timestamp()}"
    validation:
      - contains:
          code: 0
```

**一条用例能写哪些字段**（`test_cases[]` 里的每一项；除 `data` / `validation` 外都可省）：

| 字段 | 作用 | 备注 |
|---|---|---|
| `data` | 请求参数 | 放哪个位置由 `RequestHandler` 按 method + Content-Type 推断，用例不用管 |
| `validation` | 响应断言 | `contains` 是**精确等值**不是子串，yaml 里要写完整消息 |
| `extract` | 提取进变量池 | jsonpath 表达式，供后续用例 `${}` 引用 |
| `db` | 查库断言 | 声明式 `table` / `where` / `expect`，**不写 SQL** |
| `path_params` | 填 url 里的 `{占位符}` | 值内部仍可用 `${}`；填完还有残留占位符会 fail-fast |
| `headers` | **用例级**请求头 | **覆盖** `base_info.headers` 的同名项 —— 同接口鉴权不同时用（正常 / 越权 / 未登录） |
| `xfail` | 已知缺陷标记 | 填了原因 → 消费方（`cases/`）挂 `pytest.mark.xfail(strict)`；修好后 XPASS 报警 |

### 业务场景

场景 yaml 根节点是 **list**，每个元素是一个「单接口形态」的块，**顺序即执行顺序**：

```yaml
# data/scenarios/group_lifecycle.yaml（节选）
- base_info: { api_name: group-add, url: '/link-server/api/group/v1/add', method: POST, headers: {'Content-Type': 'application/json'} }
  test_cases:
    - case_name: 创建分组
      data: { title: lifecycle_g }
- base_info: { api_name: group-list, url: '/link-server/api/group/v1/list', method: GET, … }
  test_cases:
    - case_name: 查出新建组的 id
      extract: { life_id: "$.data[0].id" }   # 提取给后面用（列表按 id 倒序，刚建的在第一个）
- # … 后续步骤用 ${life_id} 引用
```

对应的测试文件里**一个函数收掉所有场景**（一个场景 = 一个 pytest 节点）：

```python
# cases/test_scenario.py
class TestScenario:
    @pytest.mark.parametrize("scenario", ScenarioModel.discover(), ids=lambda s: s.name)
    def test_scenario(self, scenario, shortlink_client, context,
                      shortlink_login, cleanup_test_data):
        ScenarioRunner(shortlink_client, context).run(scenario)
```

- **顺序由数据控制**（yaml 列表顺序），不靠 pytest 收集顺序 —— 这是和单接口最大的区别。
- **步骤间传值靠变量池**（`${life_id}`），同一套机制，没有第二套。
- **`shortlink_login` 还得挂**（token 是全局前置）；**不用 `shortlink_prepare`** —— 场景的"前置"就是它自己的第一步。
- **失败定位**：报错里带 `步骤=N/M 接口名`（`ScenarioRunner` 补的上下文）。
- **代价**：`-k` / `-m` / 重跑只能按**场景粒度**，筛不到单个 step。

### 逃生舱（流程里有 if / 循环 / 等待）

`cases/test_shortlink_flow.py` —— 短链建链是**异步受理**（`link/v1/add` 不返回 code，要轮询 `page` 等 MQ 消费），这是流程控制，直接写 Python 调 `CaseRunner`。

### 三种写法怎么选

| 特征 | 去哪 |
|---|---|
| 一条用例自己就能跑完、不依赖别人改过的状态 | **单接口** `data/api_shortlink/` |
| 步骤有先后（建了再查、改完再删、重名判重） | **场景** `data/scenarios/` |
| 流程里有 **if / 循环 / 等待**（如轮询等 MQ 消费） | **逃生舱** `cases/test_shortlink_flow.py` |

> 判据一句话：**流程线性的 → yaml；有 如果/循环/等待 → 代码**。

**为什么复用 `CaseModel`**：场景的一个 step = 单接口 yaml 的完整形态，所以 `ScenarioModel` 直接拿 `CaseModel` 解析每个元素（`CaseModel.from_dict`）——「组合」而不是「另造一套」。同理 `ScenarioRunner` 内部调 `CaseRunner`，不重写四步。

---

## 变量池与接口关联

```yaml
# 1. 提取：跑完这条用例，把响应里的 token 存进变量池
extract:
  token: $.data

# 2. 引用：后续用例用 ${token} 取值
data:
  token: "${token}"
  username: "user_${timestamp()}"     # 也能调函数
```

- **`${key}`** 变量引用（支持 `a.b.c` 点号路径）；**`${func(args)}`** 函数调用。
- 整个值恰好是一个占位符时**保留原类型**（`${count}` 取到 int 就是 int），混排在字符串里则拼接。
- 函数市场在 `src/pytest_framework/entities/context/functions.py`，加函数 = 写函数 + 挂 `@register`，框架别处不用改。
- **跨接口关联要写 fixture** —— 靠用例执行顺序不可靠（pytest 按文件名字典序收集）。

---

## 数据清理

**问题**：分组是**物理删除**、跑完不清理 → title 固定的用例**第二次跑必撞** `23001 分组名重复`；短链是逻辑删，数据越积越多。用例集于是成了"一次性"的。

**做法：快照差集**。`conftest` 的 `cleanup_test_data` fixture 在会话前后各记一份「账号下分组 / 短链的 id 快照」，收尾时把**新增的**全删掉：

```
setup:    GET /group/v1/list  → before_groups
          POST /link/v1/page  → before_links
yield     ← 跑用例
teardown: 再查一次 → 差集 = after - before
          先删短链（POST /link/v1/del）→ 再删分组（DELETE /group/v1/del/{id}）
```

- **为什么不按 title 前缀扫**：有一批用例的 title **本身就是测试点**（255 个字符、SQL 注入串、前导空格），加不了任何前缀；按 id 做差集完全不看 title 长什么样。
- **`add` 不返回 id、建链还是异步的**：所以只能靠 `list` / `page` 查；建链要等 MQ 消费，收网前**多查几轮**把漏的补上。
- ⚠️ **不是 autouse**：根 conftest 的 autouse fixture 会连 `tests/` 的框架单测一起触发，把「零外部依赖」毁掉 —— 所以**显式挂**在用例文件上。
- ⚠️ **前提：测试账号是专用的**。差集假设「跑前没有、跑后有了」＝ 本次造的；有别人往这个账号写数据会被误删。
- **清理失败只记 warning**，不改测试结论；残留用 `scripts/clean_testdata.py` 兜底 —— 它**无差别清空**账号数据，所以只对专用账号安全。

**公共前置是只读的**：`shortlink_prepare` 造的分组用 `${g1_id}` 引用，**任何用例不许删它、改它**（fixture 自己跑完会收尾删掉）。会删改分组的用例一律走**场景** —— 这是「单接口互不依赖」的落地方式。

---

## 环境配置

**边界**：用例数据（yaml 的 `data`）写「**测什么**」，换环境不该变；配置写「**在哪测**」，换环境就变。
判据：**这条值换个环境还成立吗**？不成立 → 归配置。

`config/config.yaml`（**不入库**，从 `config/config.example.yaml` 拷一份改）：

```yaml
http:
  timeout: 10

shortlink:                       # 被测环境（经网关）
  base_url: http://<测试环境网关>:8888
  phone: "<测试账号手机号>"
  pwd: "<测试账号密码>"

# 另有两段见文件内注释：db（查库校验用的库）、masking（日志脱敏的档位与凭证特征）
```

用例里用 `${...}` 引用 —— 和变量池**同一套语法**，不用记两种：

```yaml
data:
  phone: ${shortlink.phone}   # 落到配置层
  pwd:   ${shortlink.pwd}
  # token 不写在 data 里 —— 它在请求头：headers: {token: "${token}"}
```

> 注意区分：`login_post_account_login.yaml` 里「密码错误」那条的 `pwd` 是**用例数据**（故意写错）；
> 只有「登录成功」那条的账号密码才是**配置**。同一个文件里两种东西并存，靠上面的判据分开。

**真值不进文件也行** —— 用环境变量覆盖（`APP_` 前缀 + 双下划线分层）：

```bash
APP_SHORTLINK__PWD=xxx APP_SHORTLINK__PHONE=xxx ./.venv/Scripts/python.exe -m pytest
```

- 环境变量约定：`APP_` 前缀 + **双下划线**分层（`APP_LOGIN__PASSWORD` → `login.password`）。单下划线是 key 本身的一部分（`base_url`），**不分层**。
- 环境变量的值按配置里**原有值的类型**转（`timeout` 是 int，覆盖后仍是 int）。
- **`config/config.yaml` 不入库**（在 `.gitignore` 里）—— 里面是测试环境的账号和库密码。CI / Jenkins 用环境变量注入。
- 实现 `src/pytest_framework/adapters/config.py`：内部就是一个 `Context`，所以能直接当变量池的**父级**。

---

## 命令速查

```bash
# 跑接口用例（testpaths = cases）
./.venv/Scripts/python.exe -m pytest

# 跑框架自身的单测（不依赖被测服务，改 src/pytest_framework/ 后先跑这个）
./.venv/Scripts/python.exe -m pytest tests/

# 只收集不执行（条数不对时第一件事）
./.venv/Scripts/python.exe -m pytest --collect-only -q

# 按名字筛 / 按标记筛（用例 id = 接口名:用例名，中文片段就能筛）
./.venv/Scripts/python.exe -m pytest -k 分组
./.venv/Scripts/python.exe -m pytest -m smoke

# 第一个失败就停 / 失败自动重跑 / 分布式（用例必须互不依赖）
./.venv/Scripts/python.exe -m pytest -x
./.venv/Scripts/python.exe -m pytest --reruns 2 --reruns-delay 1
./.venv/Scripts/python.exe -m pytest -n 2

# 看实时日志（默认日志被 pytest 捕获，只在用例失败时显示；加 -s 实时刷屏）
./.venv/Scripts/python.exe -m pytest -s

# 兜底清理测试数据（无差别清空专用账号名下的分组 / 短链 —— 自动清理失灵时用）
./.venv/Scripts/python.exe scripts/clean_testdata.py

# 环境变量注入敏感值（优先级：环境变量 > config/config.yaml）
APP_LOGIN__PASSWORD=xxx ./.venv/Scripts/python.exe -m pytest

# 出 allure 报告：①出数据 → ②渲染静态 HTML → ③起服务看
./.venv/Scripts/python.exe -m pytest --alluredir=reports/allure-results
./tools/allure-2.46.1/bin/allure.bat generate reports/allure-results -o reports/allure-report --clean
./tools/allure-2.46.1/bin/allure.bat open reports/allure-report
```

Windows 控制台中文乱码时加 `PYTHONIOENCODING=utf-8`。

---

## 关键规则（pytest）

**pytest 靠命名发现用例，不匹配就静默跳过**（不报错、不警告）：

| 层级 | 规则 |
|---|---|
| 文件 | `test_*.py` 或 `*_test.py` |
| 函数 | 模块级 `test_*` |
| 类 | `Test*` 开头，类里不能写 `__init__` |

- **`-k` vs `-m`**：`-k` 按名字字符串筛，`-m` 按标记分类筛。名字会改、标记不会，选跑优先 `-m`。自定义标记要在 `pytest.ini` 的 `markers` 里注册。
- **`skipif` 的条件在收集阶段求值**（模块导入那一刻）—— 写成 `False` 就是死条件；里面发网络请求还会拖垮收集。
- **`skip` vs `xfail`**：`skip` 根本不跑；`xfail` 照跑但预期失败。本项目 `xfail` 用 `strict` —— **XPASS 会算失败**，是"缺陷已修复"的信号。
- **`fixture`**：定义在 `conftest.py` 里，同目录及子目录的用例写个参数名就能用，不用 import。fixture 里断言挂了，用例报 `ERROR` 不是 `FAILED`。
- **参数化**：`@pytest.mark.parametrize` 的参数名必须和函数形参**一模一样**。
- **`python 文件.py` vs `python -m 包.模块`**：前者只把**文件所在目录**放进搜索路径，后者把 **cwd** 放进去。包内相互 import 的文件必须用 `-m` 跑。

---

## 报告（allure）

allure 分两步：**pytest 出原始数据** → **allure 命令行渲染成页面**。

```bash
# 1. 跑用例 + 出原始数据
./.venv/Scripts/python.exe -m pytest --alluredir=reports/allure-results

# 2. 渲染成静态 HTML
./tools/allure-2.46.1/bin/allure.bat generate reports/allure-results -o reports/allure-report --clean

# 3. 看 —— 起本地 HTTP 服务 + 自动开浏览器
./tools/allure-2.46.1/bin/allure.bat open reports/allure-report
#   或直接从原始数据起（跳过第 2 步）
./tools/allure-2.46.1/bin/allure.bat serve reports/allure-results
```

场景会渲染成**嵌套 step**；`environment.properties` 由 `conftest` 从配置生成，**只写非敏感项**（密码绝不进报告）。

---

## CI

### GitHub Actions —— 框架单测

`.github/workflows/ci.yml`：push / PR / 手动触发，跑 `tests/`（框架单测，**零外部依赖**），出 `junit.xml` + allure 产物，跑完发通知。用 `continue-on-error` + 最后一步判 `outcome` —— **测试失败也照发通知**。

> ⚠️ **GHA 只跑 `tests/`**：`cases/` 要**外网的测试环境**，runner 够不着。接口那条链走 Jenkins。

要在 GitHub 上配的 Secrets（仓库 Settings → Secrets and variables → **Actions**，**不是 Environments**）—— 这些值只住在 GitHub，**绝不进仓库**：

| Name | 用途 |
|---|---|
| `DINGTALK_WEBHOOK` | 钉钉机器人 Webhook 地址（安全设置选**「加签」**） |
| `DINGTALK_SECRET` | 钉钉加签密钥（`SEC` 开头） |
| `SMTP_HOST` | 如 `smtp.qq.com` |
| `SMTP_PORT` | `465`（脚本走 SSL；填 587 是 STARTTLS，连不上） |
| `SMTP_USER` | 完整邮箱地址 |
| `SMTP_PASSWORD` | **授权码**，不是登录密码（QQ 邮箱要先开「IMAP/SMTP服务」） |
| `MAIL_TO` | 收件人，多个用逗号隔开 |

`MAIL_FROM` 可省（默认取 `SMTP_USER`）。**没配的渠道会被 `notify.py` 自动跳过**，本地跑不会因为缺配置而报错。
`scripts/notify.py` 是**独立脚本、不 import 框架**（CI 胶水，不是框架能力）：读 `junit.xml` → 拼消息 → 分发钉钉 / 邮件。

### Jenkins —— 接口用例

**为什么是 Jenkins 不是 GitHub Actions**：接口用例要连**内网的测试环境**，GitHub 的 runner 够不着。Jenkins 跑在工具机上，和内网通。

**job（`pytest-shortlink-api`，Freestyle）**：

| 配置 | 值 |
|---|---|
| 源码管理 | Git → Gitee 仓库，分支 `*/develop` |
| 构建触发器 | 手动（可加定时） |
| 构建环境 | 绑定凭据 → 环境变量 `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` / `APP_SHORTLINK__PWD` / `APP_SHORTLINK__PHONE` |
| Build step | 见下 |
| 构建后操作 | Publish JUnit test result report → `reports/junit.xml` |

**构建脚本**：

```bash
docker run --rm \
  -v "$WORKSPACE":/app \
  -v /data/pytest_venv:/venv \
  -e DINGTALK_WEBHOOK -e DINGTALK_SECRET -e APP_SHORTLINK__PWD -e APP_SHORTLINK__PHONE \
  -w /app \
  python:3.12-slim \
  bash -c '
    [ -x /venv/bin/python ] || python -m venv /venv
    /venv/bin/pip install -q -r requirements.txt || exit 1
    mkdir -p reports
    /venv/bin/python -m pytest cases/ --junitxml=reports/junit.xml; rc=$?
    /venv/bin/python scripts/notify.py reports/junit.xml || true
    exit $rc
  '
```

- **为什么起 `python:3.12` 容器**：Jenkins 容器里没有 Python。起个 python 容器最省事，不用改 Jenkins 本身。
- **`$WORKSPACE` 为什么能直接给 `docker run -v`**：Jenkins 容器当初是 `-v /data:/data` 挂进去的，容器里的工作区路径在宿主机上是同一个路径。
- **`/data/pytest_venv`**：依赖装在这个挂载卷里，**第二次跑就快**（首次约 2 分钟，之后 20 秒）。
- **`rc=$?` + `exit $rc`**：**用例失败时也要发通知**，发完再按原码退出 —— job 该红还是红。
- **`-e VAR`**（不带值）：从宿主环境继承，**值不落在 job 配置里**。
- **`config/config.yaml` 不入库**，所以 Jenkins 上靠 `APP_SHORTLINK__*` 环境变量注入账号（见「环境配置」）。

### 推代码（两个远端）

GitHub 是主仓库，Gitee 是 **Jenkins 的拉取源** —— 只推 GitHub 的话，Jenkins 跑的还是旧代码。

```bash
# origin 的 push 已配成两个（fetch 仍走 GitHub）
git remote -v
#   origin  git@github.com:23lpx/pytest_practice.git     (fetch)
#   origin  git@github.com:23lpx/pytest_practice.git     (push)
#   origin  git@gitee.com:li-peng-xiang-2315915034/pytest_practice.git (push)
# 之后一句 git push 同时推两边
```

> ⚠️ 配 push 地址时，`git remote set-url --add --push` 会把**继承来的**那个地址顶掉，所以要**显式把两个都 add 一遍**。

---

## 文档索引

- `docs/代码规范.md` —— 写代码前的硬约束
- `docs/架构审查.md` —— 分层基线 + 依赖判据，加模块前对照
- `docs/interface_test_framework_design_v2.md` / `docs/framework_exception_design_methodology.md` —— 设计说明

> 开发过程中的踩坑记录、进度日志和决策复盘记在 `CLAUDE.md`（给协作者 / 工具看），不放在本文件。
