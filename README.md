# 接口自动化（pytest + 自研框架）

跟 46 集接口自动化课程推进的实操仓库。**不逐集跟视频敲，按「出题 → 写代码 → 批改」的方式过。**

跑通闭环之后转向**自研一套接口测试框架**（数据驱动、分层），pytest 本身不动，只规范开发层。

---

## 被测服务

**商用短链平台**（Java / Spring Cloud 多模块），**经网关**接：

| 项 | 值 |
|---|---|
| 地址 | `http://TEST_GATEWAY_HOST:8888`（经网关，服务不对外直连） |
| 数据目录 | `data/api_shortlink/` |
| 用例入口 | `cases/test_shortlink.py` |

⚠️ **服务器按需开关**（测试应用机 + 中间件机），连不上先确认那两台机器开着。

**鉴权**：登录接口免登，返回的 token 放**请求头**（`token: <JWT>`）；缺 / 错 token → `code=250004`。测试账号配在 `config/config.yaml` 的 `shortlink` 段。

**成功判据是 `code=0`** —— 业务失败**也是 HTTP 200**，**只看响应体的 code**（`contains` 是**精确等值**，不是子串）。

> **历史**：研发期用过 `flaskServer.exe`（本地 PyQt5 mock）练手，2026-10-12 已归档到 `archive/`。
> 它是**纯内存 mock、没有数据库**（用 MySQL general_log 实测确认），所以「查库校验」那一步**它教不了** ——
> 真靶子来了之后它就从"练手"变成了"每次跑测试都得先双击它"的包袱。详见 `archive/README.md`。

### 账号与鉴权

| 项 | 值 |
|---|---|
| 手机号 | `13800000000`（`config.shortlink.phone`） |
| 密码 | `CHANGE_ME_PWD`（`config.shortlink.pwd`） |
| token 位置 | **请求头** `token: <JWT>` |

（这两个值配在 `config/config.yaml` 的 `shortlink` 段，用例 yaml 用 `${shortlink.phone}` 引用，**不写死**。）

⚠️ **鉴权用 token，不是 cookie** —— 登录响应里返回 `token` 字段，后续请求把它当**表单参数**传（不是放 header）。
缺 token → `9001 新增失败，参数缺失或token失效`。

### 接口三组

| 组 | 说明 |
|---|---|
| `/dar/user/*` | login / addUser / deleteUser / queryUser / updateUser |
| `/coupApply/cms/*` | 电商（login_dw / goodsList / productDetail / placeAnOrder 等） |
| `/api/order/*` | 物流（17 个） |

---

## 环境

Python 3.12，venv 在 `.venv/`。

```bash
./.venv/Scripts/python.exe -m pip install -r requirements.txt   # 等价于：pip install -e .[dev]
```

**依赖的唯一来源是 `pyproject.toml`**（运行依赖 + `[dev]` 依赖都写在那儿）；`requirements.txt` 现在只有一行 `-e .[dev]`，纯粹为了保住老习惯。装完之后这个包本身也是**可编辑安装**（指向 `src/` 里的源码），改代码不用重装。

> ⚠️ **不要直接敲 `pip` 或 `activate`**，一律用 `./.venv/Scripts/python.exe -m pip ...`。

---

## 框架（当前状态）

自研框架，**src-layout + 按架构层分目录**（目录名自己就说明了分层）。

```
src/pytest_framework/
├── entities/         ← 最内：零第三方依赖；模型 / 变量池 / 契约 / 异常 / 常量
├── ports/            ← 端口：内层定契约、外层实现（sender / context_store）
├── usecases/         ← 编排：case_runner / scenario_runner
├── adapters/         ← 适配：request / validation / extract / execute_case / reader / config
└── infrastructure/   ← 最外：http(requests) / logging / report(allure) / path
        ↑ 依赖方向一路向内：infrastructure → adapters → usecases → ports → entities
```

数据流（两条路径最终汇合到同一个执行器）：

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
          ├── adapters/ValidationHandler  校验（fail-fast：不过就不写变量池）
          └── adapters/ExtractHandler     提取 → entities/Context（供后续用例引用）
```

**怎么找到包**：两次保险 —— `pytest.ini` 的 `pythonpath = src`（clone 下来直接跑）+ `pyproject.toml`（`pip install -e .` 后任何地方都能 import）。

**数据驱动（两种发现，同一个模式）**：

| | 发现 | 展平？ | 结果粒度 | 谁在用 |
|---|---|---|---|---|
| 单接口 | `CaseModel.discover()` → `ExecuteCase.discover()` | ✅ 展平 | **一条 case 一个节点** | 数据驱动**主力**（量大、独立） |
| 场景 | `ScenarioModel.discover()` | ❌ 不展平 | **一个场景一个节点** | 有**先后关系**的流程（分组生命周期、重名判重） |

**加数据文件 = 加用例，代码一个字不改** —— `cases/test_shortlink.py` 把 `data/api_shortlink/` 下的用例**展平**成 pytest 节点，`cases/test_scenario.py` 则把 `data/scenarios/` 的每条场景收成**一个**节点。粒度差别就在「要不要展平」这一处。

**两条路径，一个执行器**：单接口用 pytest 参数化展开成 N 个节点，场景用 `ScenarioRunner` 收成 1 个节点。两者最终都调 `CaseRunner.run(case)` —— **它永远只跑一条，不认识"列表"、也不认识"场景"**。循环策略归调用方，执行能力归 `CaseRunner`。

| 层 | 文件 | 职责 |
|---|---|---|
| **entities** | `entities/model/` | 用例模型（`CaseModel` / `ScenarioModel`）+ `discover()` 扫目录 |
| | `entities/context/` | 变量池 / 占位符解析 / 函数市场 |
| | `entities/contracts.py` | 契约：`CaseLike`（用例形状）/ `ResponseLike`（响应形状）/ `VariableSource`（能按路径取值） |
| | `entities/exception/` | 异常体系 |
| | `entities/constants/` | 常量（魔法值收口） |
| **ports** | `ports/sender.py` | `Sender` —— 发请求的端口，`HttpClient` 实现 |
| **usecases** | `usecases/case_runner.py` | 编排单条用例（不认识"列表/场景"） |
| | `usecases/scenario_runner.py` | 场景编排（顺序 + 步骤日志，内部调 CaseRunner） |
| **adapters** | `adapters/execute_case.py` | 适配（模型 → 执行单元）+ `discover()` 展平。**不 import pytest** |
| | `adapters/request.py` | 发送请求（依赖 `Sender` 端口，**不 import requests / HttpClient**） |
| | `adapters/validation.py` | 校验 |
| | `adapters/extract.py` | 提取（jsonpath → 变量池） |
| | `adapters/reader.py` | 读 yaml → dict |
| | `adapters/config.py` | 配置加载（yaml + 环境变量覆盖），可当 `Context` 的父级 |
| **infra** | `infrastructure/http.py` | HTTP 底座（**不认识测试概念**） |
| | `infrastructure/logging/` | 日志（**含脱敏**） |
| | `infrastructure/report.py` | allure 薄封装（框架唯一认识 allure 的地方） |
| | `infrastructure/path.py` | `_project_root()` |
| — | `tests/` | 框架自身的单测（不依赖被测服务） |

**资源生命周期靠依赖注入**：`HttpClient` 由 `conftest` 的 `client` fixture（**session 级**，为连接复用）创建并 `close()`；`Context`（变量池）由 `context` fixture（**session 级**，跨用例关联必须共享）提供。`CaseRunner` / `RequestHandler` 只收不 new。整轮测试共用 1 条连接（不是每条用例一条）。

**依赖倒置：内层只认端口，不认实现** —— `adapters` / `usecases` 依赖 `ports.Sender`（端口）+ `entities.contracts.ResponseLike`（响应契约），**不 import `infrastructure.HttpClient`、也不 import `requests`**；`adapters` **不 import pytest**。全仓**只有 `conftest` 知道 `HttpClient` 存在**。判据：**内层模块的 import 里有没有出现具体库或外层类**。

**配置当变量池的父级**：`context` fixture 建的是 `Context(parent=config)` —— `${...}` 因此只有**一个入口**：`${token}` 查变量层（运行时提取的），`${shortlink.phone}` 落到配置层（`config/config.yaml`）。**配置层只读**：用例 `set` 同名 key 只写自己那层，覆盖不了配置。`Context` 只认 `VariableSource` 契约，**不认识 `Config`** —— 换任何别的来源都行。

**占位符替换必须产副本**：`resolve_case()` 返回 `ResolvedCase`，**绝不就地改原 case** —— `ExecuteCase` 是收集阶段构造、整个 session 共用的（含 `--reruns`），就地改会让第二遍跑到脏数据。

**跨用例关联靠 fixture，不靠执行顺序**：pytest 按**文件名字典序**收集，"登录先跑"天然不成立。要前置数据就声明 `conftest` 的 fixture —— `shortlink_login`（登一次写 token）、`shortlink_prepare`（造分组/域名），`cases/test_shortlink.py` 把它们挂给了所有用例（session 级只跑一次，零成本）。

**文档**：`docs/代码规范.md`（写代码前看）、`docs/架构审查.md`（分层基线 + 依赖判据，加东西前对照）、`docs/interface_test_framework_design_v2.md`、`docs/framework_exception_design_methodology.md`、`docs/修改方案.txt`

---

## 目录

| 目录 | 干什么 |
|---|---|
| `cases/` | 测试入口，三个文件：`test_shortlink.py`（单接口，数据驱动）/ `test_scenario.py`（场景）/ `test_shortlink_flow.py`（逃生舱 —— 流程里有轮询等待的那种）。**加数据文件 = 加用例** |
| `src/pytest_framework/` | **框架本体**，按架构层分目录：`entities/` `ports/` `usecases/` `adapters/` `infrastructure/` |
| `tests/` | **框架自身的单测**。不在 `testpaths` 里，要显式 `pytest tests/` |
| `data/api_shortlink/` | **单接口**数据 yaml（一个接口一个文件，`base_info` + `test_cases`）。**加文件 = 加用例** |
| `config/` | **环境配置**：`config.yaml`（短链平台地址 / 超时 / 账号 / 脱敏）。换环境改这份，用例不用动 |
| `archive/` | **归档区**：不再维护、pytest 也收不到（`testpaths = cases`）。现在装的是 flaskServer 那套，见 `archive/README.md` |
| `docs/` | 设计文档：代码规范 / 架构审查 / 设计说明 |
| `conftest.py` | **Composition Root** —— 唯一 `new` 具体实现的地方：`config` / `context` / `shortlink_client` / `shortlink_login` / `shortlink_prepare` / `db_checker` fixture + `init_logger()` |
| `pytest.ini` | pytest 配置（含 `pythonpath = src`） |
| `pyproject.toml` | 打包声明（src-layout 的包在 `src/` 下）+ 依赖清单 |
| `logs/` `reports/` | 日志（按天切，**已脱敏**）/ 报告产物，**不进 git** |
| `tools/` | 本地工具（allure 命令行），**不进 git**。各人自己解压一份 |

---

## 进度

**课程**

| 集 | 内容 | 状态 |
|---|---|---|
| 1-9 | requests / cookie / 封装 / yaml 用例 / 配置读取 | ✅ 旧仓库阶段 |
| 10-18 | pytest 基础 → 参数化 → yaml 驱动 → log 封装 | ✅ 10-07 ~ 10-08 |
| 19-24 | 框架开发项目实战 1-6 | 🔄 进行中（见下「框架」） |
| 25-46 | 数据库断言 / allure / Jenkins / 进阶工具 | ⬜ |

**自研框架（19 集之后的自主推进）**

| 阶段 | 内容 | 状态 |
|---|---|---|
| 1 | 最小闭环：Reader → Model → Runner → Client | ✅ |
| 2 | 多 case 调度权还给 pytest（一条 case = 一个 pytest 节点） | ✅ |
| 3 | Runner 瘦身 + 抽 RequestHandler / ValidationHandler | ✅ |
| 4 | 代码规范（阿里手册适配 Python）+ 异常体系 | ✅ |
| 5 | 目录语义梳理（constants / contracts / infra / exception） | ✅ |
| 6 | 依赖注入：`HttpClient` 由 session 级 fixture 注入，修掉 session 泄漏 | ✅ |
| 7 | 接口关联：`context/` 变量池 + `${}` 占位符 + `extract_handler`；日志增强（分段 / 脱敏 / 带栈） | ✅ |
| 8 | 参数位置自适应：`RequestHandler` 按 method + Content-Type 翻译成 params / json / data | ✅ |
| 9 | 单接口铺开：8 个接口 28 条用例（用户组 5 + 电商组 3） | ✅ |
| 10 | **业务场景**：`ScenarioModel` + `ScenarioRunner`，电商下单全链路跑通 | ✅ |
| 11 | **数据驱动**：两种 `discover()`（单接口展平 / 场景不展平），加文件 = 加用例；`cases/` 收到 2 个文件 | ✅ |
| 12 | **配置收敛**：`src/pytest_framework/adapters/config.py` + `config/config.yaml`；`Context` 加父级，`${...}` 一套语法同时覆盖配置与变量 | ✅ |
| 13 | **allure 报告**：场景 → 可视化**嵌套 step**；`environment.properties` 从配置生成 | ✅ |
| 14 | **目录重构**：src-layout + 按架构层分目录（entities / ports / usecases / adapters / infrastructure）；`testcase/` → `cases/`，删 `archive/` | ✅ |
| 15 | **查库校验**：`ports.QueryExecutor`（只读）+ `DbChecker` + pymysql 底座；yaml 加 `db:` 段 —— 数据校验从「看响应」扩到「看库」 | ✅ |
| 16 | **CI 自动化**：GitHub Actions（push / PR 触发）跑**框架单测** + 存 allure 产物；`scripts/notify.py` 跑完发钉钉 / 邮件 | ✅ |
| 17 | **第二个被测系统**：短链平台（Java / Spring Cloud）—— 独立 `data/api_shortlink/` 目录 + 三个 fixture；225 条用例（166 绿 / 59 xfail）；框架为此补了 4 项能力（见「下一步」） | ✅ |
| 18 | **让用例可反复跑**：快照差集清理 + 单接口公共前置改**只读** + 有依赖的流程挪进**场景** + 摘掉过时 xfail；**连跑两遍 187 绿 / 32 xfail / 0 红** | ✅ |
| 19 | **接口用例进 Jenkins**：Gitee 源码 + `python:3.12` 容器跑 + JUnit 报告表格 + 构建完自动发钉钉；**构建 SUCCESS，耗时 89 秒** | ✅ |

---

## 命令速查

```bash
# 跑接口用例（testpaths = cases）
./.venv/Scripts/python.exe -m pytest

# 本地验一次通知（不配环境变量就只打印消息、不发）
./.venv/Scripts/python.exe -m pytest tests/ --junitxml=reports/junit.xml
./.venv/Scripts/python.exe scripts/notify.py reports/junit.xml

# 兜底清理测试数据（无差别清空专用账号名下的分组/短链 —— 自动清理失灵时用）
./.venv/Scripts/python.exe scripts/clean_testdata.py

# 换环境：临时指到别的服务地址（优先级：命令行 > 环境变量 > config/config.yaml）
./.venv/Scripts/python.exe -m pytest -k login

# 敏感值用环境变量注入（APP_ 前缀 + 双下划线分层）
APP_LOGIN__PASSWORD=xxx ./.venv/Scripts/python.exe -m pytest

# 跑框架自身的单测（不依赖被测服务，改 src/pytest_framework/ 后先跑这个）
./.venv/Scripts/python.exe -m pytest tests/

# 看实时日志（默认日志被 pytest 捕获，只在用例失败时显示；加了 -s 就实时刷屏）
./.venv/Scripts/python.exe -m pytest -s

# 只收集不执行（条数不对时第一件事）
./.venv/Scripts/python.exe -m pytest --collect-only -q

# 按名字筛 / 按标记筛（用例 id = 接口名:用例名，中文片段就能筛）
./.venv/Scripts/python.exe -m pytest -k 商品详情
./.venv/Scripts/python.exe -m pytest -m smoke
./.venv/Scripts/python.exe -m pytest -m "smoke or regression"

# 第一个失败就停
./.venv/Scripts/python.exe -m pytest -x

# 失败自动重跑
./.venv/Scripts/python.exe -m pytest --reruns 2 --reruns-delay 1

# 分布式（前提：用例之间互不依赖）
./.venv/Scripts/python.exe -m pytest -n 2

# 以「模块」方式跑单个文件（file 方式会找不到包）
./.venv/Scripts/python.exe -m pytest_framework.infrastructure.logging.logger

# 出 allure 报告：①出数据 → ②渲染静态 HTML → ③起服务看
./.venv/Scripts/python.exe -m pytest --alluredir=reports/allure-results
./tools/allure-2.46.1/bin/allure.bat generate reports/allure-results -o reports/allure-report --clean
./tools/allure-2.46.1/bin/allure.bat open reports/allure-report
```

---

## 关键规则

**pytest 靠命名发现用例，不匹配就静默跳过**（不报错、不警告）：

| 层级 | 规则 |
|---|---|
| 文件 | `test_*.py` 或 `*_test.py` |
| 函数 | 模块级 `test_*` |
| 类 | `Test*` 开头，类里不能写 `__init__` |

**`-k` vs `-m`**：`-k` 按名字字符串筛，`-m` 按标记分类筛。名字会改、标记不会，选跑优先 `-m`。

**自定义标记必须在 `pytest.ini` 的 `markers` 里注册**，否则每次跑都有警告。

**`skipif` 的条件在收集阶段求值**（模块导入那一刻）—— 写成 `False` 就是死条件；里面发网络请求还会拖垮收集。

**`skip` vs `xfail`**：`skip` 根本不跑；`xfail` 照跑但预期失败。`XPASS` 默认不算失败。

**fixture**：定义在 `conftest.py` 里，同目录及子目录的用例**写个参数名就能用，不用 import**。fixture 里断言挂了，用例报 `ERROR` 不是 `FAILED`。

**参数化**：`@pytest.mark.parametrize` 的参数名必须和函数形参**一模一样**。

**`python 文件.py` vs `python -m 包.模块`** —— 前者只把**文件所在目录**放进搜索路径，后者把 **cwd** 放进去。所以包内相互 import 的文件，必须用 `-m` 跑（PyCharm 会偷偷帮你加路径，别被它骗）。

---

## 踩过的坑

**① 中文路径会让 xdist 直接崩** —— `execnet ... EOFError`。项目必须放**纯 ASCII 路径**（本仓库在 `D:\find_work\Test_develop\pytest`）。

**② venv 不能随便搬** —— 绝对路径写死在 `pyvenv.cfg` / `activate` / `pip.exe` 里。搬家后要么重建，要么永远用 `python -m pip`。

**③ PyCharm 跑得通 ≠ 命令行跑得通** —— IDE 会把项目根当 Sources Root 加进 `sys.path`，命令行不会。报 `ModuleNotFoundError` 先想这个。

**④ 控制台 print 中文是乱码，但断言是好的** —— Windows 管道 GBK 的问题。看干净输出：`PYTHONIOENCODING=utf-8`。

**⑤ 写文件别用裸相对路径** —— `open('logs/x')` 跟着 **cwd** 走，换目录跑就写错地方。统一用 `src/pytest_framework/infrastructure/path.py` 的 `_project_root()`。

**⑥ `Path('D:/proj') / '/data/x'` 会顶掉项目根** —— 前导斜杠会让 pathlib 当成绝对路径，结果是 `D:\data\x` 而不是 `D:\proj\data\x`。写 `file_path` 前先 `lstrip("/\\")`。

**⑦ 循环导入** —— 早期模型层和适配层互相 import 过一次，直接 `ImportError: partially initialized module`。单向依赖 + 必要时局部 import。

**⑧ pytest 会递归收 `testpaths` 下的目录** —— 早年的 `cases/test_/` 备份目录就被收进来过，里面 import 断了导致整个 `collection error`、**一条都不跑**。它现在归档到 `archive/`（`testpaths = cases` 收不到），`pytest.ini` 里那个 `test_` 继续留着当防御。

**⑨ `norecursedirs` 写一个值会把默认值整个顶掉** —— 只写 `test_`，pytest 默认的 `.venv` / `.*` / `*.egg` 就全失效了，`pytest .` 会把三方库自带的测试也收进来。要写就得把默认值补回来：`test_ *.egg .* venv build dist __pycache__`。

**⑩ 跨用例关联的用例集不能开 `-n`** —— 变量池（`Context`）是**进程内**的，xdist 每个 worker 各一份，A 提取的 token B 看不见；而且用例还会被重新分配到不同 worker，"谁先跑"都不保证。这是「用例间有依赖」和「分布式」的固有冲突，换任何变量池实现都解决不了。

**⑪ `contains` 是精确等值匹配，不是子串匹配** —— 断言值要写**完整消息**。响应是 `"新增失败，参数缺失或token失效"` 时，yaml 里写 `msg: 新增失败` **会挂**。（课程项目的 `contains` 是子串匹配，两者语义不同。）

**⑫ `logger.propagate = False` 会让 pytest 看不见日志** —— pytest 的日志捕获（失败时那段 `Captured log`）挂在 **root logger** 上。一旦 `propagate=False` 断了冒泡，用例失败时报告里**一条日志都没有**，控制台又被 stderr 捕获吞掉，等于瞎了。**别设它。**

**⑬ logger 级 Filter 管不到冒泡上来的日志** —— `logger.addFilter()` 只在 `Logger.handle()` 里对**直接记到该 logger** 的消息执行。框架里日志全是 `logging.getLogger(__name__)`（`pytest_framework.xxx`），挂在 `"pytest_framework"` 上的 filter 根本轮不到 —— **而且它静默失效**，不报错。要打码就挂 record 工厂（`logging.setLogRecordFactory`），从源头下手。

**⑭ `autouse` fixture 的依赖写在签名里 = 强制求值** —— fixture 的参数在**函数体之前**求值，`autouse` 又作用于整个会话，所以「签名里有 `config`」等于**每次跑 pytest 都加载配置** —— 函数体里那句 `if not 条件: return` 拦不住它。实测后果：配置文件一删，`pytest tests/` 的 **84 条框架单测全 ERROR**。要真惰性就挪进函数体：`cfg = request.getfixturevalue("config")`。（`conftest.py` 的 `_allure_environment` 踩过这个。）

**⑮ 单测别读生产配置** —— 断言一旦绑在真实值上，「改一下 `config/config.yaml`」就会把单测带崩，「框架单测零依赖」变成空话。单测要配置文件就用自己的（`tests/data/config.yaml`）。

**⑯ `LOGGER_NAME` 必须和包名一致，否则日志静默全丢** —— 各模块用 `logging.getLogger(__name__)`，名字是 `pytest_framework.xxx`，冒泡到 `pytest_framework` 就停。目录重构把包名从 `framework/` 改成 `src/pytest_framework/` 时，`LogConfig.LOGGER_NAME` 没跟着改，handler 挂在一个**永远收不到消息**的 logger 上 —— 文件日志、控制台日志**一起没了，不报错也不告警**，`logs/app.log` 停在重构前那一刻。**教训：日志这种东西，改完要真跑一次确认"它确实写进去了"，光看代码看不出来。**（脱敏不受影响 —— `install_masking` 走的是全局 `LogRecord` 工厂，不依赖 logger 名。）

**⑰ 一次 `json.dumps` 能把整条脱敏废掉** —— 脱敏有两条路（**按字段名** / **按值特征**），**两条都要求"看到结构化数据"**。而 `http.py` 的 `_brief_body` 为了日志好看，把响应 `json.dumps` 成了字符串 —— **一序列化，结构就没了，两条路全断**。短链平台正好把 token 装在 `data` 字段里（key 不叫 `token`），于是**登录凭证明文落盘**。修法：**先脱敏、再序列化**（`json.dumps(mask(body), ...)`）。
> **教训**：**"让日志好看"和"让日志安全"会互相拆台** —— 这两件事在代码里离得很远（一个在 `http.py` 的格式化，一个在 `logging/masking.py`），不真跑起来看不出来。改了日志的**呈现方式**，就要重验一遍**脱敏还灵不灵**。

---

## 接口用例怎么进 Jenkins

**为什么是 Jenkins 不是 GitHub Actions**：这 219 条用例要连**内网的测试环境**（`TEST_GATEWAY_HOST:8888`），GitHub 的 runner 够不着。Jenkins 跑在工具机（`JENKINS_HOST`）上，和内网通 —— 这是它相对 GHA **唯一但决定性**的优势（UI 比 GHA 那套老派得多，配起来绕）。

**job（`pytest-shortlink-api`，Freestyle）**：

| 配置 | 值 |
|---|---|
| 源码管理 | Git → `https://gitee.com/li-peng-xiang-2315915034/pytest_practice.git`，分支 `*/develop` |
| 构建触发器 | 手动（可加定时） |
| 构建环境 | 绑定凭据 → 环境变量 `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` |
| Build step | 见下 |
| 构建后操作 | Publish JUnit test result report → `reports/junit.xml` |

**构建脚本**：

```bash
docker run --rm \
  -v "$WORKSPACE":/app \
  -v /data/pytest_venv:/venv \
  -e DINGTALK_WEBHOOK -e DINGTALK_SECRET \
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

- **为什么起 `python:3.12` 容器**：Jenkins 容器里**没有 Python**（宿主机那个是 3.10）。起个 python 容器最省事，不用改 Jenkins 本身。
- **`$WORKSPACE` 为什么能直接给 `docker run -v`**：Jenkins 容器当初是 `-v /data:/data` 挂进去的，容器里的工作区路径在宿主机上**是同一个路径**。
- **`/data/pytest_venv`**：依赖装在这个挂载卷里，**第二次跑就快**（首次约 2 分钟，之后 20 秒）。
- **`rc=$?` + `exit $rc`**：**用例失败时也要发通知**（失败时最需要它），发完再按原码退出 —— job 该红还是红。和 GHA 那边 `continue-on-error` + 判 `outcome` 同一个思路。
- **`-e DINGTALK_WEBHOOK`**（不带值）：从宿主环境继承，值不落在 job 配置里。

**踩过的三个坑**（都是「静默失败」型的，值得记）：

1. **Jenkins 的 "Jenkins URL" 是空的** —— 不影响跑构建，但 **CLI 连接、通知里的链接**都会出错。系统配置里补上 `http://JENKINS_HOST:8080/`。
2. **配置里写错类名前缀，Jenkins 会静默丢掉整块配置** —— 凭据绑定器的类名是 `org.jenkinsci.plugins.credentialsbinding.impl.SecretBuildWrapper`，先写成了 `hudson.plugins...`，POST 上去**返回 200、但回读发现被丢了**，构建日志里也没有绑定痕迹（`ShallowClone` 那次也是同样现象）。**教训：改完 job 配置一定要回读确认。**
3. **GitHub 拉不动** —— 完整 clone 时 `fatal: expected flush after ref listing`，时好时坏（国内访问 GitHub 的常态）。**CI 的代码源不能是"看运气"的**，换 Gitee 秒级。

**推代码要推两个远端**（GitHub 是主仓库，Gitee 是 Jenkins 的拉取源）：

```bash
# origin 的 push 已配成两个（fetch 仍走 GitHub）
git remote -v
#   origin  git@github.com:23lpx/pytest_practice.git (fetch)
#   origin  git@gitee.com:li-peng-xiang-2315915034/pytest_practice.git (push)
#   origin  git@github.com:23lpx/pytest_practice.git (push)
# 之后一句 git push 同时推两边
```

> ⚠️ 配的时候有个坑：`git remote set-url --add --push` 会把**继承来的**那个 push 地址顶掉，
> 所以要**显式把两个都 add 一遍**，否则只剩最后加的那个。

---

## 下一步

**⑱ 让用例可反复跑**（进度表 18）—— **已完成**：

- **数据清理**（测试侧自己解决，没等开发）：`cleanup_test_data` 快照差集；另配 `scripts/clean_testdata.py` 兜底清存量
- **单接口独立**：公共前置 `${g1_id}` 改**只读**，会删改它的 6 条一律移进场景
- **场景化**：`data/scenarios/` 两条分组场景 + `cases/test_shortlink_flow.py` 一个短链逃生舱
- 摘掉 22 条过时 xfail（清理生效 / 前置稳定后它们真能过），删 4 条重复的重名语义

**这一轮揪出来的"碰巧过"用例**（都靠脏数据撑着，清一次库就全挂）—— 值钱的教训：

| 用例 | 假象 | 真相 |
|---|---|---|
| `创建分组：并发同时建同名（竞态）` | 绿 | 靠账号里**残留的 `race`**；清干净后建 race 得 `0` —— 判据本身就不成立（串行跑不出竞态）→ **删** |
| `更新分组：改成另一个已有分组的名字` | 绿 | 靠 `g1` **被别人删了**；实测更新接口**不查重**（返回 `0`）→ **按实测收进场景** |
| `建链：expired 格式非法` | 红（挂错理由） | 实测服务端**不校验** expired 格式、照收 → **按实测改期望** |

> **教训**：上次总结过「测出来的差异，先排除是不是我数据不对」—— 这次是它的**反面**：
> **"看起来绿"也可能是脏数据撑的**。清一遍库再跑，才看得出哪些用例是真独立的。

**还剩两件外部条件**（写在被测项目侧的 `docs/测试环境需求-给开发.md`）：

- **第二测试账号**（卡 8 条越权用例）—— 注册要短信验证码、自动化造不出来，得开发在环境里预置
- **流量额度** —— 免费包一天 3 条（本轮实测：建链用例连跑两遍都过，额度够；长期跑要盯）

**框架侧这一轮补的 4 项能力**（都是"测第二个系统"撞出来的**真实缺口**，不是为某张表打的补丁）：

| 能力 | 解决什么 |
|---|---|
| **路径参数** `path_params` | `/detail/{id}` 这类 REST 路径之前没法表达 —— 只能把具体值写进 `base_info.url`，同一接口被拆成好几个文件 |
| **用例级 headers** | 同一接口的用例鉴权不同（正常带 A 的 token、越权带 B 的、未登录不带），接口级表达不了 |
| **`xfail` 字段** | 已知缺陷/框架缺口挂标记（`strict`）：红了算预期，修好后 XPASS 报警，逼你回来摘 |
| **脱敏修复** | 见踩坑 ⑰ —— 按值特征匹配 + 先脱敏再序列化 |

**一条教训**：这一轮我把「**数据不对**导致的通用错误码」误判成了「**契约模糊点**」——
那时 `groupId` 还是没替换的占位符，请求在参数校验层就被拒了，返回 110003；**前置补齐后服务端进到业务逻辑，返回的是文档承诺的 260401**。
**测出来的差异，先排除"是不是我数据不对"，再记被测系统的账。**

---

（以下为更早的账，已结清，留档）

**查库校验已经通了**（进度表 15），但还欠两件：

1. **没有真靶子**。`flaskServer.exe` 是**纯内存 mock，压根没有库**（实测见 CLAUDE.md「被测服务」）。
   所以 `data/api/db_check_cases.yaml` 目前是**链路演示**：接口打 flaskServer、库查 docker 的 demo 库，
   两边是各自准备的数据。真实项目里两边该是同一套数据源 —— 那时这个文件就是正经用例了。
2. **测试数据管理**（真正的难点）。现在的用例是「固定值匹配」（`updateUser` 改一位就失败），
   一旦要「跑完接口再查库确认」，立刻撞上「数据从哪来 / 跑完怎么清理」。
   **优先走接口造数**（调被测系统自己的增删接口），而不是直接写库 —— 直接写库绕过了业务逻辑，
   造出来的数据真实业务里不可能存在。写库只在「测试自己的库（工作库）」时才考虑。

**⑯ 自动化集成**（进度表 16）—— **框架侧通了**：

- `.github/workflows/ci.yml`：push / PR / 手动触发，跑 `tests/`（107 条框架单测，
  **零外部依赖**），出 `junit.xml` + allure 结果，跑完发通知。
  用 `continue-on-error` + 最后一步判 `outcome` —— **测试失败也照发通知**
  （失败的时候恰恰最需要它）。
- `scripts/notify.py`：**独立脚本，不 import 框架**（它是 CI 胶水，不是框架能力）。
  读 `junit.xml` → 拼消息 → 分发钉钉 / 邮件；加渠道只加一个 `send_xxx`，
  解析和渲染一个字不用动。敏感值走 **GitHub Secrets**
  （仓库 Settings → Secrets and variables → **Actions**，**不是 Environments**），
  没配的渠道自动跳过 —— 本地跑不会因为缺配置而报错。
- ⚠️ **`cases/` 那 225 条接口用例还进不去 GitHub Actions**：它们要**外网的测试环境**
  （`TEST_GATEWAY_HOST:8888`），GitHub 的 runner 够不着。接口那条链走 **Jenkins**
  （在被测项目侧，工具机跑）—— 本仓的 GHA 只管**框架单测**。

**CI 要在 GitHub 上配的 Secrets**（仓库 Settings → Secrets and variables → **Actions**，
**不是 Environments**）—— 这些值只住在 GitHub，**绝不进仓库**：

| Name | 用途 |
|---|---|
| `DINGTALK_WEBHOOK` | 钉钉机器人 Webhook 地址（安全设置选**「加签」**） |
| `DINGTALK_SECRET` | 钉钉加签密钥（`SEC` 开头） |
| `SMTP_HOST` | 如 `smtp.qq.com` |
| `SMTP_PORT` | `465`（脚本走 SSL；填 587 是 STARTTLS，连不上） |
| `SMTP_USER` | 完整邮箱地址 |
| `SMTP_PASSWORD` | **授权码**，不是登录密码（QQ 邮箱要先开「IMAP/SMTP服务」） |
| `MAIL_TO` | 收件人，多个用逗号隔开 |

`MAIL_FROM` 可省（默认取 `SMTP_USER`）。**没配的渠道会被 `notify.py` 自动跳过** ——
本地跑不会因为缺配置而报错。

---

## 接口关联怎么用（阶段 7 产物）

```yaml
# 1. 提取：跑完这条用例，把响应里的 token 存进变量池
extract:
  token: $.token

# 2. 引用：后续用例用 ${token} 取值
data:
  token: "${token}"
  username: "user_${timestamp()}"     # 也能调函数
```

- **`${key}`** 变量引用（支持 `a.b.c` 点号路径）；**`${func(args)}`** 函数调用。
- 整个值恰好是一个占位符时**保留原类型**（`${count}` 取到 int 就是 int），混排在字符串里则拼接。
- 函数市场在 `src/pytest_framework/entities/context/functions.py`，加函数 = 写函数 + 挂 `@register`，框架别处不用改。
- **跨接口关联要写 fixture**（见 `conftest.py` 的 `login`）—— 靠用例执行顺序不可靠，原因见坑 ⑩。单接口用例现在**统一挂**这个 fixture（session 级只登一次，零成本）。

---

## 业务场景怎么用

单接口 yaml 根节点是 **dict**；**场景 yaml 根节点是列表**，每个元素是一个「单接口形态」的块，**顺序即执行顺序**：

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

对应的测试文件里就是**一个函数收掉所有场景**（一个场景 = 一个 pytest 节点）：

```python
# cases/test_scenario.py
class TestScenario:
    @pytest.mark.parametrize("scenario", ScenarioModel.discover(), ids=lambda s: s.name)
    def test_scenario(self, scenario, shortlink_client, context,
                      shortlink_login, cleanup_test_data):
        ScenarioRunner(shortlink_client, context).run(scenario)
```

- **顺序由数据控制**（yaml 列表顺序），**不靠 pytest 收集顺序** —— 这是和单接口最大的区别。
- **步骤间传值靠变量池**（`${life_id}`），同一套机制，没有第二套。
- **`shortlink_login` 还得挂**（token 是全局前置，不是业务步骤）；但**不用 `shortlink_prepare`** —— 场景的"前置"就是它自己的第一步。
- **失败定位**：报错里带 `步骤=N/M 接口名`（`ScenarioRunner` 补的上下文），一眼看出断在哪步。
- **代价**：`-k` / `-m` / 重跑只能按**场景粒度**，筛不到单个 step。

**三种写法怎么选**：

| 特征 | 去哪 |
|---|---|
| 一条用例自己就能跑完、不依赖别人改过的状态 | **单接口** `data/api_shortlink/` |
| 步骤有先后（建了再查、改完再删、重名判重） | **场景** `data/scenarios/` |
| 流程里有 **if / 循环 / 等待**（如轮询等 MQ 消费） | **逃生舱** `cases/test_shortlink_flow.py`（直接写 Python） |

> 判据一句话：**流程线性的 → yaml；有 如果/循环/等待 → 代码**。

**为什么复用 `CaseModel`**：场景的一个 step = 单接口 yaml 的完整形态，所以 `ScenarioModel` 直接拿 `CaseModel` 解析每个元素（`CaseModel.from_dict`）——「组合」而不是「另造一套」。同理 `ScenarioRunner` 内部调 `CaseRunner`，不重写四步。

---

## 数据清理怎么用

**问题**：分组是**物理删除**、跑完不清理 → title 固定的用例**第二次跑必撞** `23001 分组名重复`；短链是逻辑删，数据越积越多。**用例集于是成了"一次性"的。**

**做法：快照差集**。`conftest` 的 `cleanup_test_data` fixture 在会话前后各记一份「账号下分组/短链的 id 快照」，收尾时把**新增的**全删掉：

```
setup:    GET /group/v1/list  → before_groups
          POST /link/v1/page  → before_links
yield     ← 跑用例
teardown: 再查一次 → 差集 = after - before
          先删短链（POST /link/v1/del）→ 再删分组（DELETE /group/v1/del/{id}）
```

- **为什么不按 title 前缀扫**：有一批用例的 title **本身就是测试点**（255 个字符、SQL 注入串、前导空格），加不了任何前缀；按 id 做差集完全不看 title 长什么样。
- **`add` 不返回 id、建链还是异步的**：所以只能靠 `list` / `page` 查；建链要等 MQ 消费，收网前**多查几轮**把漏的补上。
- ⚠️ **不是 autouse**：根 conftest 的 autouse fixture 会连 `tests/` 的框架单测一起触发，把「零外部依赖」毁掉 —— 所以**显式挂**在用例文件上（同坑 ⑭）。
- ⚠️ **前提：测试账号是专用的**。差集假设「跑前没有、跑后有了」＝ 本次造的；有别人往这个账号写数据会被误删。
- **清理失败只记 warning**，不改测试结论（清理是善后，网络抖动不该让绿的变红）；残留用 `scripts/clean_testdata.py` 兜底 —— 它**无差别清空**账号数据，所以只对专用账号安全。

**公共前置是只读的**：`shortlink_prepare` 造的分组用 `${g1_id}` 引用，**任何用例不许删它、改它**（fixture 自己跑完会收尾删掉）。会删改分组的用例一律走**场景** —— 这是「单接口互不依赖」的落地方式。

---

## 配置怎么改（阶段 12 产物）

**边界**：用例数据（yaml 的 `data`）写「**测什么**」，换环境不该变；配置写「**在哪测**」，换环境就变。
判据：**这条值换个环境还成立吗**？不成立 → 归配置。

`config/config.yaml`：

```yaml
http:
  timeout: 10

shortlink:                       # 被测环境（经网关）
  base_url: http://TEST_GATEWAY_HOST:8888
  phone: "13800000000"           # 测试账号
  pwd: CHANGE_ME_PWD

# 另有两段见文件内注释：db（查库校验用的库）、masking（日志脱敏的档位与凭证特征）
```

用例里用 `${...}` 引用 —— 和变量池**同一套语法**，不用记两种：

```yaml
data:
  phone: ${shortlink.phone}   # 落到配置层
  pwd:   ${shortlink.pwd}
  # token 不写在 data 里 —— 它在请求头：headers: {token: "${token}"}
```

> 注意区分：`login_post_account_login.yaml` 里「密码错误」那条的 `pwd: definitely-wrong-pwd` 是**用例数据**（故意写错），
> 只有「登录成功」那条的账号密码才是**配置**。同一个文件里两种东西并存，靠上面的判据分开。

**优先级**：环境变量 > `config/config.yaml`。

```bash
./.venv/Scripts/python.exe -m pytest -k login
APP_LOGIN__PASSWORD=real_pwd ./.venv/Scripts/python.exe -m pytest
```

- 环境变量约定：`APP_` 前缀 + **双下划线**分层（`APP_LOGIN__PASSWORD` → `login.password`）。
  单下划线是 key 本身的一部分（`base_url`），**不分层** —— 拿它分层会把 `base_url` 拆成 `base.url`。
- 环境变量的值按配置里**原有值的类型**转（`timeout` 是 int，覆盖后仍是 int），
  否则 `"30"` 会一路传进 requests。
- 这份配置**故意提交进 git**（本地 demo 服务、账号是假的，clone 即跑更要紧）。
  **真实项目里它该进 `.gitignore`**，敏感值只走环境变量 / CI secrets。
- 实现 `src/pytest_framework/adapters/config.py`：内部就是一个 `Context`，所以能直接当变量池的**父级**。
  `Context` 只认 `VariableSource` 契约，不认识 `Config` —— 将来换成数据库 / 配置中心，`Context` 一个字不用改。

---

## 报告怎么看（阶段 13 产物）

allure 分两步：**pytest 出原始数据** → **allure 命令行渲染成页面**。

```bash
# 1. 跑用例 + 出原始数据（--alluredir 是 allure-pytest 插件注册的选项）
./.venv/Scripts/python.exe -m pytest --alluredir=reports/allure-results

# 2. 渲染成静态 HTML
./tools/allure-2.46.1/bin/allure.bat generate reports/allure-results -o reports/allure-report --clean

# 3. 看 —— 起本地 HTTP 服务 + 自动开浏览器
./tools/allure-2.46.1/bin/allure.bat open reports/allure-report
#   或直接从原始数据起（跳过第 2 步）
./tools/allure-2.46.1/bin/allure.bat serve reports/allure-results
```

⚠️ **别双击 `index.html`** —— allure 是单页应用，`file://` 下会因 CORS 白屏，**必须走 HTTP 服务**。

报告里能看到什么：

| 位置 | 内容 | 来自 |
|---|---|---|
| Behaviors | 按 `feature` / `story` 分组：`单接口` → 各接口；`业务场景` → 各场景 | `cases/*.py` 的 `@allure.feature` + `allure.dynamic.story` |
| 用例详情 | 场景的 **5 个嵌套 step**（登录→列表→详情→下单→支付），一眼看出断在哪步 | `ScenarioRunner` 的 `report.step()` |
| Environment | `base_url` / `timeout` / 账号 / Python 版本 | `conftest` 的 `_allure_environment`（从 `config` 生成） |

**两个设计点**：

1. **框架不直接 `import allure`** —— 走 `src/pytest_framework/infrastructure/report.py` 的 `step()` 薄封装。
   这是框架核心**第一次依赖外部工具**，把耦合收在一个文件里，将来换 pytest-html 只改这里。
2. **密码绝不进报告** —— `environment.properties` 只写非敏感项；报告是要发给别人看的。

`tools/allure-2.46.1/` 是本地解压的 allure 命令行（**不进 git**）—— 路径不对就换成你自己的，
或者装到系统 PATH 里。它需要 **JDK**（本机已有 Java 22）。
