# 接口自动化（pytest + 自研框架）

跟 46 集接口自动化课程推进的实操仓库。**不逐集跟视频敲，按「出题 → 写代码 → 批改」的方式过。**

跑通闭环之后转向**自研一套接口测试框架**（数据驱动、分层），pytest 本身不动，只规范开发层。

---

## 被测服务

| 项 | 值 |
|---|---|
| 程序 | `flaskServer.exe`（PyInstaller 打包的 PyQt5 GUI 程序） |
| 路径 | `D:\find_work\八股文\java后端八股文\07-项目\接口自动化\flaskServer\flaskServer\flaskServer.exe` |
| 地址 | `http://127.0.0.1:8787` |

⚠️ **每次重启电脑都要手动打开它，并点窗口里的「启动服务」按钮** —— 双击 exe 只是开了个窗口，服务不会自己起。

**怎么确认服务活着**：随便发个请求，404 也说明它在跑；连不上才是没起。

### 账号与鉴权

| 用户名 | 密码 |
|---|---|
| `test01` | `admin123` |

（这两个值配在 `config/config.yaml` 里，用例 yaml 用 `${login.username}` 引用，**不写死**。）

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
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

已装：`requests` / `pyyaml` / `jsonpath` / `pytest` / `pytest-rerunfailures` / `pytest-xdist` / `pytest-ordering` / `logging_tree`

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
data/api/*.yaml         ← 单接口（dict：base_info + test_cases）
data/scenarios/*.yaml   ← 场景（list：N 个接口块，**顺序即执行顺序**）
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
| 场景 | `ScenarioModel.discover()` | ❌ 不展平 | **一个场景一个节点** | 只做**简单线性**流程 |

**加数据文件 = 加用例，代码一个字不改** —— `cases/` 里只有两个文件：`test_api.py`（所有单接口）+ `test_scenario.py`（所有场景）。粒度差别就在「要不要展平」这一处。

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

**配置当变量池的父级**：`context` fixture 建的是 `Context(parent=config)` —— `${...}` 因此只有**一个入口**：`${token}` 查变量层（运行时提取的），`${login.username}` 落到配置层（`config/config.yaml`）。**配置层只读**：用例 `set` 同名 key 只写自己那层，覆盖不了配置。`Context` 只认 `VariableSource` 契约，**不认识 `Config`** —— 换任何别的来源都行。

**占位符替换必须产副本**：`resolve_case()` 返回 `ResolvedCase`，**绝不就地改原 case** —— `ExecuteCase` 是收集阶段构造、整个 session 共用的（含 `--reruns`），就地改会让第二遍跑到脏数据。

**跨用例关联靠 fixture，不靠执行顺序**：pytest 按**文件名字典序**收集，"登录先跑"天然不成立。要前置数据就声明 `conftest` 的 `login` fixture —— `cases/test_api.py` 给所有单接口用例都挂上了（session 级只登一次，零成本，不用再按文件声明）。

**文档**：`docs/代码规范.md`（写代码前看）、`docs/架构审查.md`（分层基线 + 依赖判据，加东西前对照）、`docs/interface_test_framework_design_v2.md`、`docs/framework_exception_design_methodology.md`、`docs/修改方案.txt`

---

## 目录

| 目录 | 干什么 |
|---|---|
| `cases/` | **只有两个文件**：`test_api.py`（收所有单接口）+ `test_scenario.py`（收所有场景）。`cases/test_/` 是老用例备份，**pytest 不收**（`norecursedirs`） |
| `src/pytest_framework/` | **框架本体**，按架构层分目录：`entities/` `ports/` `usecases/` `adapters/` `infrastructure/` |
| `tests/` | **框架自身的单测**。不在 `testpaths` 里，要显式 `pytest tests/` |
| `data/api/` | **单接口**数据 yaml（一个接口一个文件，`base_info` + `test_cases`）。**加文件 = 加用例** |
| `data/scenarios/` | **业务场景** yaml（根节点是列表，N 个接口块按顺序执行）。**加文件 = 加场景** |
| `config/` | **环境配置**：`config.yaml`（base_url / 超时 / 账号）。换环境改这份，用例不用动 |
| `docs/` | 设计文档：代码规范 / 架构审查 / 设计说明 |
| `conftest.py` | **Composition Root** —— 唯一 `new` 具体实现的地方：`config` / `base_url` / `client` / `context` / `login` fixture + `init_logger()` |
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

---

## 命令速查

```bash
# 跑接口用例（testpaths = cases）
./.venv/Scripts/python.exe -m pytest

# 换环境：临时指到别的服务地址（优先级：命令行 > 环境变量 > config/config.yaml）
./.venv/Scripts/python.exe -m pytest --base-url http://127.0.0.1:9999

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

**⑦ 循环导入** —— `model` 和 `adapter` 互相 import 过一次，直接 `ImportError: partially initialized module`。单向依赖 + 必要时局部 import。

**⑧ pytest 会递归收 `testpaths` 下的目录** —— `cases/test_/` 这种备份目录也会被收进来，里面 import 断了就整个 `collection error`，**一条都不跑**。已在 `pytest.ini` 用 `norecursedirs = test_` 排除。

**⑨ `norecursedirs` 写一个值会把默认值整个顶掉** —— 只写 `test_`，pytest 默认的 `.venv` / `.*` / `*.egg` 就全失效了，`pytest .` 会把三方库自带的测试也收进来。要写就得把默认值补回来：`test_ *.egg .* venv build dist __pycache__`。

**⑩ 跨用例关联的用例集不能开 `-n`** —— 变量池（`Context`）是**进程内**的，xdist 每个 worker 各一份，A 提取的 token B 看不见；而且用例还会被重新分配到不同 worker，"谁先跑"都不保证。这是「用例间有依赖」和「分布式」的固有冲突，换任何变量池实现都解决不了。

**⑪ `contains` 是精确等值匹配，不是子串匹配** —— 断言值要写**完整消息**。响应是 `"新增失败，参数缺失或token失效"` 时，yaml 里写 `msg: 新增失败` **会挂**。（课程项目的 `contains` 是子串匹配，两者语义不同。）

**⑫ `logger.propagate = False` 会让 pytest 看不见日志** —— pytest 的日志捕获（失败时那段 `Captured log`）挂在 **root logger** 上。一旦 `propagate=False` 断了冒泡，用例失败时报告里**一条日志都没有**，控制台又被 stderr 捕获吞掉，等于瞎了。**别设它。**

**⑬ logger 级 Filter 管不到冒泡上来的日志** —— `logger.addFilter()` 只在 `Logger.handle()` 里对**直接记到该 logger** 的消息执行。框架里日志全是 `logging.getLogger(__name__)`（`framework.xxx`），挂在 `"framework"` 上的 filter 根本轮不到 —— **而且它静默失效**，不报错。要打码就挂 record 工厂（`logging.setLogRecordFactory`），从源头下手。

**⑭ `autouse` fixture 的依赖写在签名里 = 强制求值** —— fixture 的参数在**函数体之前**求值，`autouse` 又作用于整个会话，所以「签名里有 `config`」等于**每次跑 pytest 都加载配置** —— 函数体里那句 `if not 条件: return` 拦不住它。实测后果：配置文件一删，`pytest tests/` 的 **84 条框架单测全 ERROR**。要真惰性就挪进函数体：`cfg = request.getfixturevalue("config")`。（`conftest.py` 的 `_allure_environment` 踩过这个。）

**⑮ 单测别读生产配置** —— 断言一旦绑在真实值上，「改一下 `config/config.yaml`」就会把单测带崩，「框架单测零依赖」变成空话。单测要配置文件就用自己的（`tests/data/config.yaml`）。

---

## 下一步

**MySQL 数据校验**（简历重点③）：

1. docker 拉个临时库（「需要的时候用 docker 拉一个临时用就行了」）。
2. 真正的难点**不是连库，是测试数据管理** —— 现在的用例是「固定值匹配」（`updateUser` 改一位就失败），
   一旦要「跑完接口再查库确认」，立刻撞上「数据从哪来 / 跑完怎么清理」。
3. 设计「yaml 里怎么描述 DB 期望」—— 比接口断言多一层（数据流扩出 `db` 那一路）。

（再往后：自动化集成 —— CI 里跑框架单测 + 接口用例。）

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

## 业务场景怎么用（阶段 10 产物）

单接口 yaml 根节点是 **dict**；**场景 yaml 根节点是列表**，每个元素是一个「单接口形态」的块，**顺序即执行顺序**：

```yaml
# data/scenarios/xxx.yaml
- base_info: { api_name: 登录, url: /coupApply/cms/login_dw, method: POST, headers: {…} }
  test_cases:
    - case_name: 登录
      data: { username: test123, password: qwe666 }
      extract: { user_token: $.data.user_token }     # 提取给后面用
- base_info: { api_name: 商品列表, url: /coupApply/cms/goodsList, method: GET, headers: {…} }
  test_cases:
    - case_name: 获取商品列表
      data: { msgType: getHandsetListOfCust, page: 1, size: 20 }
      extract: { goods_id: $.goodsList[0].goodsId }
- # … 后续步骤引用 ${goods_id}
```

对应的测试文件里就是**一个函数**（一个场景 = 一个 pytest 节点）：

```python
# cases/test_scenario.py —— 一个函数收掉**所有**场景
class TestScenario:
    @pytest.mark.parametrize("scenario", ScenarioModel.discover(), ids=lambda s: s.name)
    def test_scenario(self, scenario, client, context):
        ScenarioRunner(client, context).run(scenario)
```

- **顺序由数据控制**（yaml 列表顺序），**不靠 pytest 收集顺序** —— 这是和单接口最大的区别。
- **步骤间传值靠变量池**（`${user_token}` / `${goods_id}`），同一套机制，没有第二套。
- **不需要 `login` fixture** —— 顺序天然成立，「前置」就是第一步。
- **失败定位**：报错里带 `步骤=3/5 商品详情`（`ScenarioRunner` 补的上下文），一眼看出断在哪步。
- **代价**：`-k` / `-m` / 重跑只能按**场景粒度**，筛不到单个 step。

**为什么复用 `CaseModel`**：场景的一个 step = 单接口 yaml 的完整形态，所以 `ScenarioModel` 直接拿 `CaseModel` 解析每个元素（`CaseModel.from_dict`）——「组合」而不是「另造一套」。同理 `ScenarioRunner` 内部调 `CaseRunner`，不重写四步。

---

## 配置怎么改（阶段 12 产物）

**边界**：用例数据（yaml 的 `data`）写「**测什么**」，换环境不该变；配置写「**在哪测**」，换环境就变。
判据：**这条值换个环境还成立吗**？不成立 → 归配置。

`config/config.yaml`：

```yaml
base_url: http://127.0.0.1:8787

http:
  timeout: 10

login:                 # 只有「正确的账号密码」进配置
  username: test01
  password: admin123
```

用例里用 `${...}` 引用 —— 和变量池**同一套语法**，不用记两种：

```yaml
data:
  user_name: ${login.username}   # 落到配置层
  passwd:    ${login.password}
  token:     ${token}            # 走变量层（运行时提取的）
```

> 注意区分：`login_cases.yaml` 里「密码错误」那条的 `passwd: wrong` 是**用例数据**（故意写错），
> 只有「登录成功」那条的账号密码才是**配置**。同一个文件里两种东西并存，靠上面的判据分开。

**优先级**：命令行 `--base-url` > 环境变量 > `config/config.yaml`。

```bash
./.venv/Scripts/python.exe -m pytest --base-url http://127.0.0.1:9999
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
