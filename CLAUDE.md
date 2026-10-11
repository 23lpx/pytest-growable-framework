# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是一个「学习项目」，不是普通业务仓库

用户在跟着 46 集接口自动化课程自学 pytest，**方式是「出题 → 自己写代码 → 批改」**。跑通闭环后转向**自研接口测试框架**（`src/pytest_framework/`），pytest 本身不动，只规范开发层。

- **不要直接替他把代码写完**。默认先讲思路、给方向；他写完后你批改（找 bug、指出不规范、讲清为什么）。除非他明确说「帮我写」「直接改」。
- **全程用中文交流**。
- 他的水平：能独立写 yaml 驱动 + fixture + 参数化，现在在搭自己的框架，已经能讨论分层、依赖方向、契约设计。
- **`README.md` 是进度日志和避坑清单**，改动前后读一遍；每完成一个阶段，进度表、目录表要同步更新。
- **`docs/代码规范.md` 是写代码的硬约束**，动 `src/pytest_framework/` 前先看。
- **`docs/架构审查.md` 是分层基线和依赖判据** —— 加新模块 / 想抽接口前先对照它（尤其「有意的逆流，别动」那节，别把刻意的耦合当成 bug 修掉）。

## 运行与开发命令

Python 3.12，venv 在 `.venv/`。**必须用 `.venv` 里的解释器跑，禁止裸敲 `pip` / `activate`**（venv 搬过家，绝对路径写死在 `activate` / `pip.exe` 里）：

```bash
./.venv/Scripts/python.exe -m pytest                                  # 跑接口用例（testpaths=cases）
./.venv/Scripts/python.exe -m pytest tests/                           # 跑框架自身的单测（不依赖被测服务）
./.venv/Scripts/python.exe -m pytest --collect-only -q                # 只收集不执行（用例数不对时第一件事）
./.venv/Scripts/python.exe -m pytest -k 商品详情                        # 按名字筛（用例 id = 接口名:用例名）
./.venv/Scripts/python.exe -m pytest -m smoke                          # 按标记筛
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
- Claude Code 提的 commit，message 结尾带 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。

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

data/api/*.yaml          ← 单接口（dict：base_info + test_cases）
data/scenarios/*.yaml    ← 场景（list：N 个接口块，**顺序即执行顺序**）
   │
   ├─ 单接口 ── CaseModel.discover() 扫目录
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
         │  adapters/reader.YamlRead.read
         ▼
       entities/ScenarioModel                    = list[CaseModel]（复用单接口解析器，只是拼积木）
         │
         ▼
       usecases/ScenarioRunner                   顺序编排 + 步骤日志（整个场景 = 一个节点）
         │  ── 逐步调用 ──┐
         └────────────────┴──▶  usecases/CaseRunner.run(case)   编排，四步  ← 两条路径在此汇合
                                  ├── entities/context/replacer.resolve_case  解析 ${...} → 产出**副本**（绝不改原 case）
                                  ├── adapters/RequestHandler   依赖 ports/Sender ← infrastructure/HttpClient 实现
                                  ├── adapters/ValidationHandler  校验（fail-fast：不过就不写变量池）
                                  └── adapters/ExtractHandler     提取 → entities/Context（供后续用例引用）
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
| **usecases/**（编排：一次测试怎么跑） | |
| `usecases/case_runner.py` | 只做编排：解析占位符 → 发送 → 校验 → 提取。**不循环、不管生命周期、不认识"列表/场景"** |
| `usecases/scenario_runner.py` | 场景编排：按 yaml 顺序逐步调 `CaseRunner`；步骤日志；失败补「第 N/M 步」上下文。**不重写四步** |
| **adapters/**（适配：翻译） | |
| `adapters/execute_case.py` | 适配。`ExecuteCase` 带接口级+用例级信息，`from_model()` / `discover()`。**不 import pytest** |
| `adapters/request.py` | `RequestHandler.send(case)`。依赖 `ports.Sender`，**不 import `HttpClient` / `requests`** |
| `adapters/validation.py` | `ValidationHandler.validate(case, resp)` —— 校验，抛 `ValidationError` |
| `adapters/extract.py` | `ExtractHandler.extract(case, resp, ctx)` —— jsonpath 提取，写进变量池 |
| `adapters/reader.py` | 读 yaml → dict。抛 `YamlReadError` |
| `adapters/config.py` | 环境配置。`Config.load()` 读 yaml + 叠环境变量覆盖；**内部是 `Context`**，可直接当变量池的父级 |
| **infrastructure/**（最外，具体库都在这） | |
| `infrastructure/http.py` | HTTP 底座（session / timeout / base_url 拼接 / 日志）。**不认识测试概念** |
| `infrastructure/logging/` | `logger.py`（命名 logger + 脱敏）+ `masking.py` |
| `infrastructure/report.py` | allure 薄封装 —— **框架唯一认识 allure 的地方** |
| `infrastructure/path.py` | `_project_root()`，定位项目根 |
| **仓库其余部分** | |
| `cases/` | 测试用例：`test_api.py`（收所有单接口）+ `test_scenario.py`（收所有场景）。`cases/test_/` 是老用例备份，**pytest 不收** |
| `tests/` | **框架自身的单测**（不依赖被测服务）。裸跑 pytest 收不到，要 `pytest tests/` |
| `data/api/` | **单接口**数据 yaml（一个接口一个文件，`base_info` + `test_cases`）。**加文件 = 加用例** |
| `data/scenarios/` | **业务场景** yaml（根节点是列表，N 个接口块按顺序）。**加文件 = 加场景** |
| `config/config.yaml` | **环境配置**（base_url / timeout / 账号）。换环境只改这份。真实项目该进 `.gitignore` |
| `pyproject.toml` | 打包声明（src-layout 的包在 `src/` 下）+ 依赖清单 |
| `tools/` | 本地工具（allure 命令行），**不进 git**。各人自己解压一份 |

**关键边界**：`HttpClient` 是通用底座，只认纯值（method/path/headers/data），**不许 import 模型**；谁要 `CaseModel`，谁就在 `adapters` / `usecases` 里。

**依赖倒置：内层只认端口，不认实现**：`adapters` / `usecases` 依赖的是 `ports.Sender`（端口）+ `entities.contracts.ResponseLike`（响应契约），**不 import `infrastructure.HttpClient`、也不 import `requests`** —— 全仓只有 `conftest` 知道 `HttpClient` 存在。同理 `adapters` 不 import pytest。判据：**内层模块的 import 里有没有出现具体库或外层类**。

**资源生命周期靠依赖注入**：`HttpClient` 由 `conftest` 的 `client` fixture（**session 级**，为连接复用）创建并 `close()`；`Context`（变量池）由 `context` fixture（**session 级**，跨用例关联必须共享）提供。`CaseRunner` / `RequestHandler` **只收不 new**，不持有生命周期。改动时别把 `new HttpClient` 塞回框架内部。

**占位符替换必须产副本**：`resolve_case()` 返回 `ResolvedCase`，**绝不就地改原 case** —— `ExecuteCase` 是收集阶段构造、整个 session 共用的（含 `--reruns`），就地改会让第二遍跑到第一遍留下的脏数据。

**跨用例关联靠 fixture，不靠执行顺序**：pytest 按**文件名字典序**收集，"登录先跑"天然不成立。要前置数据就写 `conftest` 的 `login` fixture（`cases/test_api.py` 给所有单接口用例都挂上了 —— session 级只登一次，零成本）。

**数据驱动的边界（用户定调，别越界）**：**单接口是数据驱动主力**（量大、独立、一条 case 一个节点）；**场景只做简单线性流程** —— 场景 yaml 里**不许出现 if / 分支 / 循环**。需要流程控制的（重试、等待、条件跳过）**用代码写**（在 `cases/` 里直接写 test 函数调 `CaseRunner`，即"逃生舱"，和数据用例共存）。判据：**流程线性的 → yaml；有 如果/循环/等待 → 代码**。

**单接口 vs 场景 = 两种消费方式，一个执行器**：单接口用 pytest 参数化展开成 N 个节点（保住 `-k` / `-m` / 单条重跑）；场景用 `ScenarioRunner` 收成 1 个节点（**顺序由 yaml 列表决定**）。**两条路径最终都调 `CaseRunner.run(case)` —— 它永远只跑一条**。所以「加场景」不需要动 `usecases` / `adapters` / `infrastructure`：循环策略归调用方，执行能力归 `CaseRunner`。场景的每个 step 就是「单接口 yaml 的完整形态」，`ScenarioModel` 直接复用 `CaseModel.from_dict` 解析（**组合，不是继承**）。

**参数位置在 `RequestHandler` 决定，不在 `HttpClient`**：`case.data` 是「位置未定」的抽象参数，由 `RequestHandler` 按 method（GET/DELETE → params）+ Content-Type（含 json → json body，否则表单）翻译成 requests 的具体参数位。`HttpClient` 是通用底座，**只认"发什么"、不问"为什么这么发"** —— 决策归适配层，执行归底座。

**配置 vs 用例数据**：用例数据（yaml 的 `data`）写「**测什么**」，配置（`config/config.yaml`）写「**在哪测**」。判据：**这条值换个环境还成立吗**？不成立 → 归配置。⚠️ 同一个 yaml 里两种东西会并存 —— `login_cases.yaml` 的「登录成功」用 `${login.username}` 引配置，而「密码错误」的 `passwd: wrong` 是用例数据。**配置层只读**：`Context.set` 只写自己那层，覆盖不了它。

**配置和变量池是同一条查找链**：`conftest` 的 `context` fixture 建的是 `Context(parent=config)` —— `${login.username}` 落配置层、`${token}` 走变量层，**一套语法**。`Context` 只认 `contracts.VariableSource` 契约，**不认识 `Config`**：将来配置换成数据库 / 配置中心，`Context` 一个字不用改。

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
└── ValidationError       Handler：校验失败
```

Runner 捕获 `FrameworkError` → 补 `case_name` 上下文 + 记日志 → 原样 `raise`，由 pytest 判失败。

## 被测服务

`flaskServer.exe`（PyInstaller 打包的 PyQt5 GUI），`http://127.0.0.1:8787`。**重启电脑后要手动双击 exe 并点窗口里的「启动服务」**，光开窗口服务不会自己起。账号 `test01` / `admin123`（配在 `config/config.yaml`，用例里用 `${login.username}` 引用）。

**鉴权用 token，不是 cookie**：登录响应返回 `token`，后续请求把它当**表单参数**传（不是放 header）；缺/错 token → `9001 新增失败，参数缺失或token失效`。

## 排查顺序

- 用例没跑 / 数量不对 → 先 `--collect-only -q`（十有八九是命名不匹配、参数化没对上，或被 `norecursedirs` 排掉了）
- `ModuleNotFoundError` → 先想 `-m` vs 直接跑文件
- 整个 session 一条都不跑 → 看是不是有别的测试目录被收进来报 `collection error`
- 改了 `src/pytest_framework/` 后行为不对 → 确认改的是哪一层，别把测试专属逻辑塞进 `infrastructure/`
- `${...}` 报 `ContextError` → 变量池里没这个 key（没提取到 / 提取时的 key 名对不上），去文件日志 `logs/app.log` 看提取那几行
- 数据库/接口断言"看起来过了但没验到" → 注意 `contains` 是**精确等值**匹配（不是子串），yaml 里要写完整消息
- 跨用例关联在 `-n` 下失效 → 变量池是进程内的，有依赖的用例集别开 `-n`
- **日志看不见了** → 两条路查：① logger 不能设 `propagate = False`（会切断 pytest 挂 root 的日志捕获）；② 默认不加 `-s`，日志只在用例失败时以 `Captured log` 形式出现，要看实时就加 `-s`
- 控制台输出挤成一团 → 检查 `addopts` 里有没有 `-s`（有的话日志会糊在 pytest 那行未结束的用例 id 后面）
- 场景失败看不出断在第几步 → 报错上下文里有 `步骤=N/M` + 接口名（`ScenarioRunner` 补的）；加 `-s` 还能看到每步的 `--- 步骤 N/M: xxx ---` 日志
