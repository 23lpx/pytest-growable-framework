# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是一个「学习项目」，不是普通业务仓库

用户在跟着 46 集接口自动化课程自学 pytest，**方式是「出题 → 自己写代码 → 批改」**。跑通闭环后转向**自研接口测试框架**（`src/pytest_framework/`），pytest 本身不动，只规范开发层。

- **不要直接替他把代码写完**。默认先讲思路、给方向；他写完后你批改（找 bug、指出不规范、讲清为什么）。除非他明确说「帮我写」「直接改」。
- **全程用中文交流**。
- 他的水平：能独立写 yaml 驱动 + fixture + 参数化，现在在搭自己的框架，已经能讨论分层、依赖方向、契约设计。
- **`README.md` 是给外人看的门面**（本仓库**公开**）—— 只写**读者需要的事实**：项目是什么、怎么装怎么跑、目录与分层、用例怎么写、CI 怎么配。**不写第一人称的复盘 / 教训 / 进度流水账**，措辞用陈述句（不要"我""这一轮""值得记""踩过"）。
- **本文件（CLAUDE.md）承接开发笔记**：踩坑记录、进度日志、决策复盘、待办 —— 都写这儿（见文末「开发笔记」节），别往 README 塞。每完成一个阶段，README 里**与事实相关**的部分（结构 / 命令 / 配置描述）要跟着更新，但**只写事实，不写心路**。
- **`docs/代码规范.md` 是写代码的硬约束**，动 `src/pytest_framework/` 前先看。
- **`docs/架构审查.md` 是分层基线和依赖判据** —— 加新模块 / 想抽接口前先对照它（尤其「有意的逆流，别动」那节，别把刻意的耦合当成 bug 修掉）。

## 运行与开发命令

Python 3.12，venv 在 `.venv/`。**必须用 `.venv` 里的解释器跑，禁止裸敲 `pip` / `activate`**（venv 搬过家，绝对路径写死在 `activate` / `pip.exe` 里）：

```bash
./.venv/Scripts/python.exe -m pytest                                  # 跑接口用例（testpaths=cases）
./.venv/Scripts/python.exe -m pytest tests/                           # 跑框架自身的单测（不依赖被测服务）
./.venv/Scripts/python.exe -m pytest tests/ --junitxml=reports/junit.xml   # 出 junit 结果（CI 里就喂给通知脚本）
./.venv/Scripts/python.exe scripts/notify.py reports/junit.xml        # 本地验通知：不配环境变量就只打印、不发
./.venv/Scripts/python.exe -m pytest --collect-only -q                # 只收集不执行（用例数不对时第一件事）
./.venv/Scripts/python.exe -m pytest -k 分组                           # 按名字筛（用例 id = 接口名:用例名）
./.venv/Scripts/python.exe -m pytest -m smoke                          # 冒烟集（改完代码先跑它 —— 7 条，几秒钟）
./.venv/Scripts/python.exe -m pytest --reruns 2 --reruns-delay 1       # 失败重跑
./.venv/Scripts/python.exe -m pytest -n 2                              # 分布式（用例必须互不依赖）
./.venv/Scripts/python.exe -m pip install -e .                         # 可编辑安装（可选，见下「src-layout」）
./.venv/Scripts/python.exe -m pytest --alluredir=reports/allure-results  # 出 allure 原始数据
./tools/allure-2.46.1/bin/allure.bat open reports/allure-report         # 看报告（别双击 index.html，file:// 会白屏）
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Windows 控制台中文乱码时加 `PYTHONIOENCODING=utf-8`。

## Git 工作流

- **平时在 `develop` 分支开发**，一版做完再合进 `main`。
- `main` 只放「已完成的版本」，**不直接在 main 上开发 / 提交**。
- 提交前 `pytest` 要绿。
- 推上去后 **GitHub Actions 跑框架单测**（`.github/workflows/ci.yml`）；**接口用例走 Jenkins**（工具机）—— 用例要连**内网**的测试环境，GHA 的 runner 够不着，Jenkins 和内网通。配置细节见本文「CI / 部署配置」节。
- ⚠️ **`git push` 会同时推 GitHub 和 Gitee**（`origin` 配了两个 push 地址）：GitHub 是主仓库，Gitee 是 **Jenkins 的拉取源** —— **只推 GitHub 的话，Jenkins 跑的还是旧代码**。想单独推某个远端要显式指定。
- Claude Code 提的 commit，message 结尾带 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- ⚠️ **敏感信息一律不入库**：服务器地址 / IP、账号密码、token / webhook 密钥，走 `config/config.yaml`（**不入库**，模板 `config/config.example.yaml`）或环境变量 / CI secrets —— **不许写进代码、用例数据、文档、注释、commit message**。判据还是那条「换个环境还成立吗」：账号密码不成立，就归本地 / secrets。
- ⚠️ **本仓库是公开的（GitHub + Gitee），而且"事后删掉"很晚** —— 历史里的值仍能按旧 commit SHA 取到。2026-10-13 就踩过：`config/config.yaml` 带着测试账号、库密码和服务器地址进了公开仓库，得 `filter-repo` 洗历史 + 强推才收敛，GitHub 上的旧 SHA 至今仍可访问。

```bash
git checkout develop                    # 日常都在 develop
# ...写代码、跑测试...
git commit -m "..."
git push origin develop                 # 推 develop

# 一版做好 -> 合进 main
git checkout main
git merge --no-ff develop               # --no-ff 留一个合并点，标出版本边界
git push origin main
git checkout develop                    # 切回来继续
```

## 架构：单向分层，数据驱动

数据流是单向的，改代码前先想清楚动的是哪一层：

```
结构：src/pytest_framework/
   entities/  ← 最内（零第三方依赖）   ports/  ← 端口（内层定、外层实现）
   usecases/  adapters/  infrastructure/（最外，具体库都在这）

data/api_shortlink/*.yaml  ← 单接口（dict：base_info + test_cases）
data/scenarios/*.yaml      ← 场景（list：N 个接口块，**顺序即执行顺序**）⚠️ **当前没有数据文件**
   │
   ├─ 单接口 ── CaseModel.discover("data/api_shortlink") 扫目录
   │     │  adapters/reader.YamlRead.read        读文件 → dict
   │     ▼
   │   entities/CaseModel                        封装：dict → 统一模型 {api, cases[]}
   │     │
   │     ▼
   │   adapters/ExecuteCase.from_model           适配：模型 → 执行器契约（一条 = 一个执行单元）
   │     │  ExecuteCase.discover() **展平**
   │     ▼
   │   pytest 参数化                              ← 多 case 调度权在 pytest 手里
   │     每条 case 一个节点（保住 -k / -m / 重跑 / -n）
   │
   └─ 场景 ── ScenarioModel.discover() 扫目录（**不展平**）
         ✅ **有先后关系的流程走这里**：`data/scenarios/group_*.yaml`
            —— 原来那套 flaskServer 电商场景已归档到 `archive/`
         │  adapters/reader.YamlRead.read
         ▼
       entities/ScenarioModel                    = list[CaseModel]（复用单接口解析器，只是拼积木）
         │
         ▼
       usecases/ScenarioRunner                   顺序编排 + 步骤日志（整个场景 = 一个节点）
         │  ── 逐步调用 ──┐
         └────────────────┴──▶  usecases/CaseRunner.run(case)   编排，五步  ← 两条路径在此汇合
                                  ├── entities/context/replacer.resolve_case  解析 ${...} → 产出**副本**（绝不改原 case）
                                  ├── adapters/RequestHandler     依赖 ports/Sender ← infrastructure/HttpClient 实现
                                  ├── usecases/ValidationHandler  校验**响应**（fail-fast：不过就不写变量池）
                                  ├── adapters/DbChecker          校验**库**（yaml 的 db 段；没写就跳过）
                                  └── usecases/ExtractHandler     提取 → entities/Context（供后续用例引用）
```

| 目录 / 文件 | 职责 |
|---|---|
| **entities/**（最内，零第三方依赖） | |
| `entities/model/case_model.py` | 封装。`ApiCase` / `TestCase` / `CaseModel`（一个接口 + 它的用例）。抛 `CaseParseError`。`from_dict()` 供场景层复用 |
| `entities/model/scenario_model.py` | 场景解析。根节点 list → `list[CaseModel]`。**只解析，不编排** |
| `entities/context/context.py` | `Context` —— 内存变量池。`a.b.c` 点号路径，取不到抛 `ContextError` |
| `entities/context/replacer.py` | `ResolvedCase` + `resolve_case()` —— 解析 `${token}` / `${today()}`，**产副本** |
| `entities/context/functions.py` | 函数市场：`@register("today")`，加函数不用改框架 |
| `entities/contracts.py` | 契约：`CaseLike`（用例形状）、`ResponseLike`（响应形状）、`VariableSource`（能按路径取值 —— 被 `Context` 自己用，所以**留这儿、不进 ports**） |
| `entities/exception/` | 异常体系（`base.py` + `errors.py`） |
| `entities/constants/` | 常量，魔法值收口（一个主题一个模块） |
| **ports/**（端口：内层定契约、外层实现） | |
| `ports/sender.py` | `Sender` —— 「能把一个请求发出去」。`infrastructure/http.py` 实现它，`conftest` 注入 |
| `ports/query.py` | `QueryExecutor` —— 「能把一条 SQL 打出去、拿回行」。**只读**（只开 `query`、不开写）。`infrastructure/db.py` 实现它，`conftest` 注入 |
| **usecases/**（编排：一次测试怎么跑 + 应用规则） | |
| `usecases/case_runner.py` | 只做编排：解析占位符 → 发送 → 校验响应 → 校验库 → 提取。**不循环、不管生命周期、不认识"列表/场景"** |
| `usecases/scenario_runner.py` | 场景编排：按 yaml 顺序逐步调 `CaseRunner`；步骤日志；失败补「第 N/M 步」上下文。**不重写四步** |
| `usecases/validation.py` | `ValidationHandler.validate(case, resp)` —— 校验**响应**，抛 `ValidationError`。**应用规则**（比对两个内存 dict，不跨边界） |
| `usecases/extract.py` | `ExtractHandler.extract(case, resp, ctx)` —— jsonpath 提取，写进变量池。同上，**不跨边界** |
| **adapters/**（适配：**跨边界的格式转换**） | |
| `adapters/execute_case.py` | 适配。`ExecuteCase` 带接口级+用例级信息，`from_model()` / `discover()`。**不 import pytest** |
| `adapters/request.py` | `RequestHandler.send(case)`。依赖 `ports.Sender`，**不 import `HttpClient` / `requests`** |
| `adapters/db_checker.py` | `DbChecker.check(list)` —— 校验**库**：声明式期望 → SQL → 比对。**yaml 里不写 SQL**，SQL 由它生成 |
| `adapters/reader.py` | 读 yaml → dict。抛 `YamlReadError` |
| `adapters/config.py` | 环境配置。`Config.load()` 读 yaml + 叠环境变量覆盖；**内部是 `Context`**，可直接当变量池的父级 |
| **infrastructure/**（最外，具体库都在这） | |
| `infrastructure/http.py` | HTTP 底座（session / timeout / base_url 拼接 / 日志）。**不认识测试概念** |
| `infrastructure/logging/` | `logger.py`（命名 logger + 脱敏）+ `masking.py` |
| `infrastructure/report.py` | allure 薄封装 —— **框架唯一认识 allure 的地方** |
| `infrastructure/path.py` | `_project_root()`，定位项目根 |
| `infrastructure/db.py` | MySQL 底座（pymysql / DictCursor / 断线重连）。**不认识测试概念**，只认 SQL |
| **仓库其余部分** | |
| `cases/` | 测试用例：`test_shortlink.py`（单接口，数据驱动）/ `test_scenario.py`（场景）/ `test_shortlink_flow.py`（逃生舱 —— 流程里有轮询等待的那种）。**加数据文件 = 加用例，不用写测试函数** |
| `tests/` | **框架自身的单测**（不依赖被测服务）。裸跑 pytest 收不到，要 `pytest tests/` |
| `data/api_shortlink/` | **单接口**数据 yaml（一个接口一个文件，`base_info` + `test_cases`）。**加文件 = 加用例** |
| `archive/` | **归档区**：不再维护、pytest 也收不到（`testpaths = cases`）。现在装的是 flaskServer 那套。见 `archive/README.md` |
| `data/scenarios/` | **业务场景** yaml（根节点是列表，N 个接口块按顺序）。**有先后关系的流程放这儿**（如分组生命周期、重名判重）；一个场景 = 一个 pytest 节点 |
| `config/config.yaml` | **环境配置**（base_url / timeout / 账号）。**不入库**（在 `.gitignore` 里），模板见 `config/config.example.yaml`；真值也可走环境变量 `APP_*` |
| `pyproject.toml` | 打包声明（src-layout 的包在 `src/` 下）+ 依赖清单 |
| `tools/` | 本地工具（allure 命令行），**不进 git**。各人自己解压一份 |
| `.github/workflows/ci.yml` | **CI**（push / PR / 手动触发）：跑**框架单测** + 存 allure 产物 + 发通知。用 `continue-on-error` + 最后判 `outcome`，保证**测试失败也照发通知**。**只跑 `tests/`** —— `cases/` 要外网的测试环境，runner 够不着 |
| `scripts/notify.py` | **CI 胶水**：`junit.xml` → 解析 → 拼消息 → 分发钉钉 / 邮件。**独立脚本、不 import 框架** —— 它不该认识 `CaseRunner` 这些概念。敏感值走 GitHub Secrets（`Settings → Secrets and variables → Actions`，**不是 Environments**），没配的渠道自动跳过 |

**关键边界**：`HttpClient` 是通用底座，只认纯值（method/path/headers/data），**不许 import 模型**；谁要 `CaseModel`，谁就在 `adapters` / `usecases` 里。

**一条用例能写哪些字段**（`test_cases[]` 里的每一项；除 `data` / `validation` 外都可省）：

| 字段 | 作用 | 备注 |
|---|---|---|
| `data` | 请求参数 | 放哪个位置由 `RequestHandler` 按 method + Content-Type 推断，用例不用管 |
| `validation` | 响应断言 | `contains` 是**精确等值**不是子串，yaml 里要写完整消息 |
| `extract` | 提取进变量池 | jsonpath 表达式，供后续用例 `${}` 引用 |
| `db` | 查库断言 | 声明式 `table` / `where` / `expect`，**不写 SQL** |
| `path_params` | 填 url 里的 `{占位符}` | 值内部仍可用 `${}`；**填完还有残留占位符会 fail-fast** |
| `headers` | **用例级**请求头 | **覆盖** `base_info.headers` 的同名项 —— 同接口鉴权不同时用（正常/越权/未登录） |
| `xfail` | 已知缺陷标记 | 填了原因 → 消费方（`cases/`）挂 `pytest.mark.xfail(strict)`；修好后 XPASS 报警 |
| `smoke` | 冒烟标记 | 填 `true` → 消费方挂 `pytest.mark.smoke`。**只标「服务活着没」那几条**，别把正常路径全标上 —— 冒烟集一胖就退化成全量跑，失去「改完先跑一遍」的意义 |

**依赖倒置：内层只认端口，不认实现**：`adapters` / `usecases` 依赖的是 `ports.Sender`（端口）+ `entities.contracts.ResponseLike`（响应契约），**不 import `infrastructure.HttpClient`、也不 import `requests`** —— 全仓只有 `conftest` 知道 `HttpClient` 存在。同理 `adapters` 不 import pytest。判据：**内层模块的 import 里有没有出现具体库或外层类**。

**资源生命周期靠依赖注入**：`HttpClient` 由 `conftest` 的 `client` fixture（**session 级**，为连接复用）创建并 `close()`；`Context`（变量池）由 `context` fixture（**session 级**，跨用例关联必须共享）提供。`CaseRunner` / `RequestHandler` **只收不 new**，不持有生命周期。改动时别把 `new HttpClient` 塞回框架内部。

**占位符替换必须产副本**：`resolve_case()` 返回 `ResolvedCase`，**绝不就地改原 case** —— `ExecuteCase` 是收集阶段构造、整个 session 共用的（含 `--reruns`），就地改会让第二遍跑到第一遍留下的脏数据。

**跨用例关联靠 fixture，不靠执行顺序**：pytest 按**文件名字典序**收集，"登录先跑"天然不成立。要前置数据就写 `conftest` 的 fixture —— `shortlink_login`（登一次写 token）/ `shortlink_prepare`（造**只读**的公共前置：专用分组 + 官方域名），`cases/test_shortlink.py` 把它们挂给了所有用例（session 级只跑一次，零成本）。

**公共前置只读，跑完要清理 —— 这是「用例可反复跑」的两块地基**：

- **只读前置**：`shortlink_prepare` 建的 `${g1_id}` 谁都不许删、不许改 —— 会删改分组的用例一律走**场景**（自己造一次性数据）。这是「单接口互不依赖」的落地方式：依赖一个**稳定的只读前置**不算互相依赖，依赖一个**会被别人改掉的状态**才是（曾出过事：`group_delete` 按字典序排第一，把 fixture 建的组删了，后面 31 条引用它的用例全断）。
- **快照差集清理**：`cleanup_test_data` fixture 在会话前后各记一份「账号下分组/短链的 id 快照」，**差集 = 本次造的一律删**（先短链、后分组）。**为什么不按 title 前缀扫**：有一批用例的 title 本身就是测试点（255 个字符、SQL 注入串、前导空格），加不了前缀；按 id 做差集完全不看 title 长什么样。⚠️ 它**不是 autouse**（根 conftest 的 autouse 会连 `tests/` 的框架单测一起触发，把「零外部依赖」毁掉），**要显式挂**。清理失败只记 warning、不改测试结论；残留用 `scripts/clean_testdata.py` 兜底。

**数据驱动的边界（用户定调，别越界）**：**单接口是数据驱动主力**（量大、独立、一条 case 一个节点）；**场景只做简单线性流程** —— 场景 yaml 里**不许出现 if / 分支 / 循环**。需要流程控制的（重试、等待、条件跳过）**用代码写**（在 `cases/` 里直接写 test 函数调 `CaseRunner`，即"逃生舱"，和数据用例共存）。判据：**流程线性的 → yaml；有 如果/循环/等待 → 代码**。

**单接口 vs 场景 = 两种消费方式，一个执行器**：单接口用 pytest 参数化展开成 N 个节点（保住 `-k` / `-m` / 单条重跑）；场景用 `ScenarioRunner` 收成 1 个节点（**顺序由 yaml 列表决定**）。**两条路径最终都调 `CaseRunner.run(case)` —— 它永远只跑一条**。所以「加场景」不需要动 `usecases` / `adapters` / `infrastructure`：循环策略归调用方，执行能力归 `CaseRunner`。场景的每个 step 就是「单接口 yaml 的完整形态」，`ScenarioModel` 直接复用 `CaseModel.from_dict` 解析（**组合，不是继承**）。

**参数位置在 `RequestHandler` 决定，不在 `HttpClient`**：`case.data` 是「位置未定」的抽象参数，由 `RequestHandler` 按 method（GET/DELETE → params）+ Content-Type（含 json → json body，否则表单）翻译成 requests 的具体参数位。`HttpClient` 是通用底座，**只认"发什么"、不问"为什么这么发"** —— 决策归适配层，执行归底座。

**配置 vs 用例数据**：用例数据（yaml 的 `data`）写「**测什么**」，配置（`config/config.yaml`）写「**在哪测**」。判据：**这条值换个环境还成立吗**？不成立 → 归配置。⚠️ 同一个 yaml 里两种东西会并存 —— `login_cases.yaml` 的「登录成功」用 `${login.username}` 引配置，而「密码错误」的 `passwd: wrong` 是用例数据。**配置层只读**：`Context.set` 只写自己那层，覆盖不了它。

**配置和变量池是同一条查找链**：`conftest` 的 `context` fixture 建的是 `Context(parent=config)` —— `${login.username}` 落配置层、`${token}` 走变量层，**一套语法**。`Context` 只认 `contracts.VariableSource` 契约，**不认识 `Config`**：将来配置换成数据库 / 配置中心，`Context` 一个字不用改。

**数据库断言的两条纪律**：① **yaml 里不写 SQL** —— 只写 `table` / `where` / `expect`，SQL 由 `adapters/db_checker.py` 生成。SQL 一进 yaml，用例就绑死在表结构上，改个字段名要翻遍所有数据文件。② **端口只读** —— `QueryExecutor` 只开 `query`、不开写。**验证永远只读**；造数 / 清理是另一件事，**优先走接口**（调被测系统自己的增删接口），别直接写库 —— 直接写库绕过了业务逻辑，造出来的数据真实业务里不可能存在，拿它断言等于测了个寂寞。直接写库只在「测试自己的库（工作库）」时才考虑。

**查库校验和响应校验并列，是两条通道**：响应是服务**说自己做了什么**，库是它**实际做了什么**，两句话之间的差正是查库断言存在的理由。`db_checker` 可以为 `None` —— 没配数据库时纯接口用例照样跑，只有声明了 `db:` 断言的用例才会撞上配置缺失。

**报告不直接 `import allure`**：`ScenarioRunner` 写步骤走 `src/pytest_framework/infrastructure/report.py` 的 `step()` 薄封装 —— 这是框架核心**第一次依赖外部工具**，耦合收在这一个文件里，将来换 pytest-html 只改这里。⚠️ `conftest` 生成的 `environment.properties` **只写非敏感项**，密码绝不进报告（报告要发给别人看）。

## 代码规范（硬约束，详见 `docs/代码规范.md`）

- **魔法值**：不裸写字符串常量，统一放 `src/pytest_framework/entities/constants/`（如 `ValidationOp.CONTAINS`，不写 `'contains'`）。
- **函数**：每个函数标返回类型（`-> None` / `-> list[ExecuteCase]`）；有返回值的必须显式 `return`，无返回值的**不写**裸 `return`。
- **跨层契约用 Protocol**：`src/pytest_framework/entities/contracts.py`，不靠隐式鸭子类型。
- **单向依赖**，禁止反向依赖和循环 import。
- **禁止吞异常**。底层把异常转成本层框架异常，`raise ... from e` 保留原错。不要 `except: pass`，也不要在 `except` 里 `print` 完接着跑。
- **注释解释「为什么」**；公开类/函数写 docstring（做什么 + 不做什么）；**注释掉的代码直接删**，不留尸体。
- 命名：类大驼峰、函数/变量小写下划线、常量全大写、内部方法单下划线前缀。

## 异常体系

见 `docs/framework_exception_design_methodology.md`：

```
FrameworkError（基类，带 context，上层可 add_context 补充如 case_name）
├── ConfigError
├── DataError
│   ├── YamlReadError     Reader：文件不存在 / yaml 格式错 / 编码错
│   └── CaseParseError    Model：用例结构不符规范 / 字段缺失
├── ModelError
├── ContextError          Context：变量不存在 / 路径中间层类型不对 / 占位符语法
├── RequestError          Client：网络 / 超时 / 请求异常
├── ExtractError          Handler：提取失败 / jsonpath 无匹配
├── ValidationError       校验失败：响应没达预期，或库里查到的和期望对不上
└── DatabaseError         库本身出问题：连不上 / SQL 语法错 / 表名列名非法
```

Runner 捕获 `FrameworkError` → 补 `case_name` 上下文 + 记日志 → 原样 `raise`，由 pytest 判失败。

## 被测服务

**商用短链平台**（Java / Spring Cloud 多模块），**经网关**（地址见 `config/config.yaml` 的 `shortlink.base_url`）。**服务器按需开关**，连不上先确认那两台机器开着。

- **仓库在 Gitee**（不是 GitHub）—— 它的 CI/CD 用 **Jenkins**（工具机），不是 GitHub Actions（**GHA 够不着 Gitee**）。细节见那个项目自己的文档
- **鉴权**：token 放**请求头**（`token: <JWT>`），登录接口免登录；缺/错 token → `250004 账号未登录`
- **成功判据是 `code=0`** —— 业务失败**也是 HTTP 200**，**只看响应体的 code**
- **路径参数**用 `path_params`（见「一条用例能写哪些字段」），如 `/detail/{groupId}` + `path_params: {groupId: "${g1_id}"}`
- **公共前置**由 `shortlink_prepare` fixture 造（**只读**）：一个专用分组 + 官方域名 → 变量池 `${g1_id}` / `${domain_id}`。**用例不许删它、改它** —— 要删改分组就走场景；fixture 跑完自己把它删掉
- **契约模糊点与已知缺陷**都记在 yaml 的注释 / `xfail` 里 —— 改这批用例前先看那两处，别把「已知的」当成「新发现的」

### 归档：flaskServer（研发期的靶场）

早期用过一个 `flaskServer.exe`（本地 PyQt5 mock，`127.0.0.1:8787`）练手，**2026-10-12 归档到 `archive/`**。
它是**纯内存 mock、没有任何数据库**（2026-10-11 用 MySQL general_log 实测确认），所以「查库校验」那一步**它教不了**；
真靶子（短链平台）来了之后它就从"练手"变成了"包袱"（每次跑测试都得先双击它）。
**需要查当年怎么写的就看 `archive/`，别拿来跑**（`pytest.ini` 的 `testpaths = cases` 收不到它）。

## 排查顺序

- 用例没跑 / 数量不对 → 先 `--collect-only -q`（十有八九是命名不匹配、参数化没对上，或被 `norecursedirs` 排掉了）
- `ModuleNotFoundError` → 先想 `-m` vs 直接跑文件
- 整个 session 一条都不跑 → 看是不是有别的测试目录被收进来报 `collection error`
- 改了 `src/pytest_framework/` 后行为不对 → 确认改的是哪一层，别把测试专属逻辑塞进 `infrastructure/`
- `${...}` 报 `ContextError` → 变量池里没这个 key（没提取到 / 提取时的 key 名对不上），去文件日志 `logs/app.log` 看提取那几行
- **短链平台用例大面积报 `250004 账号未登录`** → 先看 `shortlink_login` 拿到 token 没有：它取登录 yaml 的**第一条**，**第一条必须是成功登录且带 `extract`**（调整顺序前先看那条注释）
- **短链平台用例报"路径参数没填全"** → `path_params` 漏给，或它引用的变量池 key 没有（`shortlink_prepare` fixture 没造出前置）
- 数据库/接口断言"看起来过了但没验到" → 注意 `contains` 是**精确等值**匹配（不是子串），yaml 里要写完整消息
- 跨用例关联在 `-n` 下失效 → 变量池是进程内的，有依赖的用例集别开 `-n`
- `db:` 断言报 `DatabaseError` → 先查**配置和容器**（`config/config.yaml` 的 `db` 段、docker 起没起），**别去改断言** —— 那是环境坏了，不是用例失败
- **日志看不见了** → 三条路查：① logger 不能设 `propagate = False`（会切断 pytest 挂 root 的日志捕获）；② 默认不加 `-s`，日志只在用例失败时以 `Captured log` 形式出现，要看实时就加 `-s`；③ **`LogConfig.LOGGER_NAME` 必须和包名一致** —— 各模块 `getLogger(__name__)` 得到 `pytest_framework.xxx`，冒泡到 `pytest_framework` 就停，名字写错 handler 就形同虚设，日志**静悄悄全丢**（改包名时最容易忘，目录重构真断过一次）
- 控制台输出挤成一团 → 检查 `addopts` 里有没有 `-s`（有的话日志会糊在 pytest 那行未结束的用例 id 后面）
- 场景失败看不出断在第几步 → 报错上下文里有 `步骤=N/M` + 接口名（`ScenarioRunner` 补的）；加 `-s` 还能看到每步的 `--- 步骤 N/M: xxx ---` 日志

---

# 开发笔记

> ⚠️ **这一节是给协作者 / 工具看的**（第一人称、复盘、时间线都在这儿），**不要搬进 `README.md`** —— README 只写事实，面向公开读者。
> 内容原本长在 README 里，2026-10-13 挪过来。

## 进度日志

**课程**：1-9 ✅（requests / cookie / 封装 / yaml 用例 / 配置读取，旧仓库阶段）；10-18 ✅（pytest 基础 → 参数化 → yaml 驱动 → log 封装，10-07 ~ 10-08）；19-24 🔄（框架开发项目实战 —— 即本仓库自研框架的起点）；25-46 ⬜。

**自研框架**（19 集之后的自主推进）：

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
| 10 | 业务场景：`ScenarioModel` + `ScenarioRunner`，电商下单全链路跑通 | ✅ |
| 11 | 数据驱动：两种 `discover()`（单接口展平 / 场景不展平），加文件 = 加用例 | ✅ |
| 12 | 配置收敛：`adapters/config.py` + `config/config.yaml`；`Context` 加父级 | ✅ |
| 13 | allure 报告：场景 → 可视化嵌套 step；`environment.properties` 从配置生成 | ✅ |
| 14 | 目录重构：src-layout + 按架构层分目录；`testcase/` → `cases/` | ✅ |
| 15 | 查库校验：`ports.QueryExecutor`（只读）+ `DbChecker` + pymysql 底座 | ✅ |
| 16 | CI 自动化：GitHub Actions 跑框架单测 + `scripts/notify.py` 发钉钉 / 邮件 | ✅ |
| 17 | 第二个被测系统：短链平台（Java / Spring Cloud），225 条用例（166 绿 / 59 xfail） | ✅ |
| 18 | 让用例可反复跑：快照差集清理 + 公共前置只读 + 流程进场景 + 摘过时 xfail（连跑两遍 187 绿 / 32 xfail / 0 红） | ✅ |
| 19 | 接口用例进 Jenkins：Gitee 源码 + `python:3.12` 容器 + JUnit 报告 + 钉钉通知（构建 SUCCESS，89 秒） | ✅ |
| 20 | 敏感信息移出仓库：`config/config.yaml` 不入库 + `filter-repo` 洗历史 + 强推（详见坑 ⑱） | ✅ |

## 踩过的坑

**① 中文路径会让 xdist 直接崩** —— `execnet ... EOFError`。项目必须放**纯 ASCII 路径**。

**② venv 不能随便搬** —— 绝对路径写死在 `pyvenv.cfg` / `activate` / `pip.exe` 里。搬家后要么重建，要么永远用 `python -m pip`。

**③ PyCharm 跑得通 ≠ 命令行跑得通** —— IDE 会把项目根当 Sources Root 加进 `sys.path`，命令行不会。报 `ModuleNotFoundError` 先想这个。

**④ 控制台 print 中文是乱码，但断言是好的** —— Windows 管道 GBK 的问题。看干净输出：`PYTHONIOENCODING=utf-8`。

**⑤ 写文件别用裸相对路径** —— `open('logs/x')` 跟着 **cwd** 走，换目录跑就写错地方。统一用 `infrastructure/path.py` 的 `_project_root()`。

**⑥ `Path('D:/proj') / '/data/x'` 会顶掉项目根** —— 前导斜杠会让 pathlib 当成绝对路径，结果是 `D:\data\x` 而不是 `D:\proj\data\x`。写 `file_path` 前先 `lstrip("/\\")`。

**⑦ 循环导入** —— 早期模型层和适配层互相 import 过一次，直接 `ImportError: partially initialized module`。单向依赖 + 必要时局部 import。

**⑧ pytest 会递归收 `testpaths` 下的目录** —— 早年的 `cases/test_/` 备份目录就被收进来过，里面 import 断了导致整个 `collection error`、**一条都不跑**。它现在归档到 `archive/`（`testpaths = cases` 收不到），`pytest.ini` 里那个 `test_` 继续留着当防御。

**⑨ `norecursedirs` 写一个值会把默认值整个顶掉** —— 只写 `test_`，pytest 默认的 `.venv` / `.*` / `*.egg` 就全失效了，`pytest .` 会把三方库自带的测试也收进来。要写就得把默认值补回来：`test_ *.egg .* venv build dist __pycache__`。

**⑩ 跨用例关联的用例集不能开 `-n`** —— 变量池（`Context`）是**进程内**的，xdist 每个 worker 各一份，A 提取的 token B 看不见；而且用例还会被重新分配到不同 worker，"谁先跑"都不保证。这是「用例间有依赖」和「分布式」的固有冲突，换任何变量池实现都解决不了。

**⑪ `contains` 是精确等值匹配，不是子串匹配** —— 断言值要写**完整消息**。（课程项目的 `contains` 是子串匹配，两者语义不同。）

**⑫ `logger.propagate = False` 会让 pytest 看不见日志** —— pytest 的日志捕获（失败时那段 `Captured log`）挂在 **root logger** 上。一旦 `propagate=False` 断了冒泡，用例失败时报告里**一条日志都没有**，控制台又被 stderr 捕获吞掉，等于瞎了。**别设它。**

**⑬ logger 级 Filter 管不到冒泡上来的日志** —— `logger.addFilter()` 只在 `Logger.handle()` 里对**直接记到该 logger** 的消息执行。框架里日志全是 `logging.getLogger(__name__)`（`pytest_framework.xxx`），挂在 `"pytest_framework"` 上的 filter 根本轮不到 —— 而且它**静默失效**，不报错。要打码就挂 record 工厂（`logging.setLogRecordFactory`），从源头下手。

**⑭ `autouse` fixture 的依赖写在签名里 = 强制求值** —— fixture 的参数在**函数体之前**求值，`autouse` 又作用于整个会话，所以「签名里有 `config`」等于**每次跑 pytest 都加载配置** —— 函数体里那句 `if not 条件: return` 拦不住它。实测后果：配置文件一删，`pytest tests/` 的框架单测**全 ERROR**。要真惰性就挪进函数体：`cfg = request.getfixturevalue("config")`。（`conftest.py` 的 `_allure_environment` 踩过这个。）

**⑮ 单测别读生产配置** —— 断言一旦绑在真实值上，「改一下 `config/config.yaml`」就会把单测带崩，「框架单测零依赖」变成空话。单测要配置文件就用自己的（`tests/data/config.yaml`）。

**⑯ `LOGGER_NAME` 必须和包名一致，否则日志静默全丢** —— 各模块用 `logging.getLogger(__name__)`，名字是 `pytest_framework.xxx`，冒泡到 `pytest_framework` 就停。目录重构把包名从 `framework/` 改成 `src/pytest_framework/` 时，`LogConfig.LOGGER_NAME` 没跟着改，handler 挂在一个**永远收不到消息**的 logger 上 —— 文件日志、控制台日志**一起没了，不报错也不告警**，`logs/app.log` 停在重构前那一刻。**教训：日志这种东西，改完要真跑一次确认"它确实写进去了"，光看代码看不出来。**

**⑰ 一次 `json.dumps` 能把整条脱敏废掉** —— 脱敏有两条路（按字段名 / 按值特征），**两条都要求"看到结构化数据"**。而 `http.py` 的 `_brief_body` 为了日志好看，把响应 `json.dumps` 成了字符串 —— 一序列化，结构就没了，两条路全断。短链平台正好把 token 装在 `data` 字段里（key 不叫 `token`），于是**登录凭证明文落盘**。修法：**先脱敏、再序列化**（`json.dumps(mask(body), ...)`）。
> **教训**：**"让日志好看"和"让日志安全"会互相拆台** —— 这两件事在代码里离得很远（一个在 `http.py` 的格式化，一个在 `logging/masking.py`），不真跑起来看不出来。改了日志的**呈现方式**，就要重验一遍**脱敏还灵不灵**。

**⑱ 敏感信息进了公开仓库，"删掉"也晚** —— `config/config.yaml` 带着**测试账号 + 库密码**，连同 README 里的**网关 IP、Jenkins 工具机 IP**，一起提交进了**公开**仓库（GitHub + Gitee）。那份文件当时还特意注释着"故意提交进 git：clone 下来配好就能跑比较重要" —— 等于把"方便"排在了"安全"前面。发现后只能 `filter-repo` 洗历史 + 强推，**而且旧值仍留在 GitHub 的旧 commit 里（按 SHA 至今取得到）** —— 真算完还得**轮换凭据**。
> **教训**：判断该不该入库的口径只有一个 —— 「**换个环境还成立吗**」。账号密码、服务器地址不成立，就该归 `.gitignore` + `config.example.yaml` + 环境变量 / CI secrets，**代码、用例、文档、注释、commit message 里都不写**。
>
> **⑲ 顺带摸出来的**：`config/config.yaml` 进了 `.gitignore` 之后，`git checkout` / `git merge` **会把它当可覆盖对象直接清掉**（换分支时真丢过一次，值只在本地就没了）。真值别只存这一个文件，放密码管理器 / 环境变量更稳。

## 待办与复盘

**这一轮（18）做完的**：数据清理（`cleanup_test_data` 快照差集 + `scripts/clean_testdata.py` 兜底）；单接口独立（公共前置 `${g1_id}` 改**只读**，会删改它的 6 条移进场景）；场景化（2 条分组场景 + 1 个短链逃生舱）；摘掉 22 条过时 xfail、删 4 条重复的重名语义。

**"碰巧过"的用例**（都靠脏数据撑着，清一次库就全挂）：

| 用例 | 假象 | 真相 |
|---|---|---|
| `创建分组：并发同时建同名（竞态）` | 绿 | 靠账号里**残留的 `race`**；清干净后建 race 得 `0` —— 判据本身就不成立（串行跑不出竞态）→ **删** |
| `更新分组：改成另一个已有分组的名字` | 绿 | 靠 `g1` **被别人删了**；实测更新接口**不查重**（返回 `0`）→ **按实测收进场景** |
| `建链：expired 格式非法` | 红（挂错理由） | 实测服务端**不校验** expired 格式、照收 → **按实测改期望** |

> **教训**：早先总结过「测出来的差异，先排除是不是我数据不对」—— 这次是它的**反面**：**"看起来绿"也可能是脏数据撑的**。清一遍库再跑，才看得出哪些用例是真独立的。

**早先的一次误判**：把「**数据不对**导致的通用错误码」当成了「**契约模糊点**」—— 那时 `groupId` 还是没替换的占位符，请求在参数校验层就被拒了，返回 110003；**前置补齐后服务端进到业务逻辑，返回的是文档承诺的 260401**。**测出来的差异，先排除"是不是我数据不对"，再记被测系统的账。**

**框架侧补的 4 项能力**（都是"测第二个系统"撞出来的真实缺口，不是为某张表打的补丁）：`path_params`（REST 路径参数）、用例级 `headers`（同接口不同鉴权）、`xfail` 字段（已知缺陷挂标记，`strict`）、脱敏修复（见坑 ⑰）。

**等外部条件的**（需求写在被测项目侧的 `docs/测试环境需求-给开发.md`）：

- **第二测试账号** —— 卡 8 条越权用例（注册要短信验证码，自动化造不出来）
- **流量额度** —— 免费包一天 3 条（建链用例连跑两遍都过，额度够；长期跑要盯）

**框架侧还欠的**（框架缺口，不是用例问题）：跳转类断言（302 / Location，10 条 xfail）。

## CI / 部署配置

> 原在 README 里，2026-10-13 随「README 只留对外内容」一起挪过来 —— 这些是**运维细节**，不是给读者看的。

**GitHub Actions**（`.github/workflows/ci.yml`）：push / PR / 手动触发 → 跑 `tests/` → 出 junit + allure 产物 → 发通知。用 `continue-on-error` + 最后一步判 `outcome`，**测试失败也照发通知**。只跑 `tests/`（`cases/` 要内网，runner 够不着）。

要在 GitHub 上配的 Secrets（Settings → Secrets and variables → **Actions**，**不是 Environments**）—— 这些值只住在 GitHub，**绝不进仓库**：

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

**Jenkins job（`pytest-shortlink-api`，Freestyle）**

| 配置 | 值 |
|---|---|
| 源码管理 | Git → Gitee 仓库，分支 `*/develop` |
| 构建触发器 | 手动（可加定时） |
| 构建环境 | 绑定凭据 → 环境变量 `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` / `APP_SHORTLINK__PWD` / `APP_SHORTLINK__PHONE` |
| Build step | 见下 |
| 构建后操作 | Publish JUnit test result report → `reports/junit.xml` |

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
- **`config/config.yaml` 不入库**，所以 Jenkins 上靠 `APP_SHORTLINK__*` 环境变量注入账号。

**两个远端**：`origin` 的 push 配了两个地址（GitHub 是主仓库，Gitee 是 Jenkins 的拉取源），一句 `git push` 同时推两边。

```bash
git remote -v
#   origin  git@github.com:23lpx/pytest_practice.git                   (fetch)
#   origin  git@github.com:23lpx/pytest_practice.git                   (push)
#   origin  git@gitee.com:li-peng-xiang-2315915034/pytest_practice.git (push)
```

⚠️ 配的时候 `git remote set-url --add --push` 会把**继承来的**那个 push 地址顶掉，要**显式把两个都 add 一遍**。
⚠️ 洗敏感值那次**强推过历史**，Jenkins workspace 里是旧 checkout —— **下次第一次构建可能要手工 wipe workspace**。

