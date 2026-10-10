# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是一个「学习项目」，不是普通业务仓库

用户在跟着 46 集接口自动化课程自学 pytest，**方式是「出题 → 自己写代码 → 批改」**。跑通闭环后转向**自研接口测试框架**（`framework/`），pytest 本身不动，只规范开发层。

- **不要直接替他把代码写完**。默认先讲思路、给方向；他写完后你批改（找 bug、指出不规范、讲清为什么）。除非他明确说「帮我写」「直接改」。
- **全程用中文交流**。
- 他的水平：能独立写 yaml 驱动 + fixture + 参数化，现在在搭自己的框架，已经能讨论分层、依赖方向、契约设计。
- **`README.md` 是进度日志和避坑清单**，改动前后读一遍；每完成一个阶段，进度表、目录表要同步更新。
- **`docs/代码规范.md` 是写代码的硬约束**，动 `framework/` 前先看。

## 运行与开发命令

Python 3.12，venv 在 `.venv/`。**必须用 `.venv` 里的解释器跑，禁止裸敲 `pip` / `activate`**（venv 搬过家，绝对路径写死在 `activate` / `pip.exe` 里）：

```bash
./.venv/Scripts/python.exe -m pytest                                  # 跑接口用例（testpaths=testcase）
./.venv/Scripts/python.exe -m pytest tests/                           # 跑框架自身的单测（不依赖被测服务）
./.venv/Scripts/python.exe -m pytest --collect-only -q                # 只收集不执行（用例数不对时第一件事）
./.venv/Scripts/python.exe -m pytest -k login                          # 按名字筛
./.venv/Scripts/python.exe -m pytest -m smoke                          # 按标记筛
./.venv/Scripts/python.exe -m pytest --reruns 2 --reruns-delay 1       # 失败重跑
./.venv/Scripts/python.exe -m pytest -n 2                              # 分布式（用例必须互不依赖）
./.venv/Scripts/python.exe -m framework.infra.logger                   # 跑单模块：包内 import 必须用 -m
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
data/*.yaml
   │  reader/YamlRead.read                    读文件 → dict
   ▼
model/CaseModel                              封装：dict → 统一模型 {api, cases[]}
   │
   ▼
adapter/ExecuteCase.from_model               适配：模型 → 执行器契约（一条 = 一个 pytest 节点）
   │
   ▼
pytest 参数化                                 ← 多 case 调度权在 pytest 手里
   │  一次一条 case
   ▼
runner/CaseRunner.run(case)                  编排，四步
   ├── context/replacer.resolve_case    解析 ${...} → 产出**副本**（绝不改原 case）
   ├── handler/RequestHandler  → client/HttpClient → 被测接口
   ├── handler/ValidationHandler        校验（fail-fast：不过就不写变量池）
   └── handler/ExtractHandler           提取 → context/Context（供后续用例引用）
```

| 目录 / 文件 | 职责 |
|---|---|
| `framework/reader/read_yaml.py` | 读文件 → dict。抛 `YamlReadError` |
| `framework/model/case_model.py` | 封装。`ApiCase` / `TestCase` / `CaseModel`。抛 `CaseParseError` |
| `framework/adapter/execute_case.py` | 适配。`ExecuteCase` 带接口级+用例级信息，`from_model()` / `to_pytest_param()` |
| `framework/runner/case_runner.py` | 只做编排：解析占位符 → 发送 → 校验 → 提取。不循环、不管生命周期 |
| `framework/handler/request_handler.py` | `RequestHandler.send(case)` —— 发请求那一步 |
| `framework/handler/validation_handler.py` | `ValidationHandler.validate(case, resp)` —— 校验，抛 `ValidationError` |
| `framework/handler/extract_handler.py` | `ExtractHandler.extract(case, resp, ctx)` —— jsonpath 提取，写进变量池 |
| `framework/context/context.py` | `Context` —— 内存变量池。`a.b.c` 点号路径，取不到抛 `ContextError` |
| `framework/context/replacer.py` | `ResolvedCase` + `resolve_case()` —— 解析 `${token}` / `${today()}`，**产副本** |
| `framework/context/functions.py` | 函数市场：`@register("today")`，加函数不用改框架 |
| `framework/client/http_client.py` | 通用 HTTP 底座（session / timeout / base_url 拼接 / 日志）。**不认识测试概念** |
| `framework/exception/` | 异常体系（`base.py` + `errors.py`） |
| `framework/constants/` | 常量，魔法值收口（一个主题一个模块） |
| `framework/contracts.py` | 跨层契约 `CaseLike`（Protocol） |
| `framework/infra/` | 基础设施：`logger.py`（命名 logger + 脱敏）/ `masking.py` / `path.py` |
| `tests/` | **框架自身的单测**（不依赖被测服务）。裸跑 pytest 收不到，要 `pytest tests/` |
| `archive/` | 归档的旧链路参考代码 + 被取代的旧设计文档。**不要 import 它** |

**关键边界**：`HttpClient` 是通用底座，只认纯值（method/path/headers/data），**不许 import 模型**；谁要 `CaseModel`，谁就在 `adapter` / `runner` / `handler` 里。

**资源生命周期靠依赖注入**：`HttpClient` 由 `conftest` 的 `client` fixture（**session 级**，为连接复用）创建并 `close()`；`Context`（变量池）由 `context` fixture（**session 级**，跨用例关联必须共享）提供。`CaseRunner` / `RequestHandler` **只收不 new**，不持有生命周期。改动时别把 `new HttpClient` 塞回框架内部。

**占位符替换必须产副本**：`resolve_case()` 返回 `ResolvedCase`，**绝不就地改原 case** —— `ExecuteCase` 是收集阶段构造、整个 session 共用的（含 `--reruns`），就地改会让第二遍跑到第一遍留下的脏数据。

**跨用例关联靠 fixture，不靠执行顺序**：pytest 按**文件名字典序**收集（`test_add_user.py` 排在 `test_login.py` 前），"登录先跑"天然不成立。要前置数据就写 `conftest` 的 `login` fixture。

## 代码规范（硬约束，详见 `docs/代码规范.md`）

- **魔法值**：不裸写字符串常量，统一放 `framework/constants/`（如 `ValidationOp.CONTAINS`，不写 `'contains'`）。
- **函数**：每个函数标返回类型（`-> None` / `-> list[ExecuteCase]`）；有返回值的必须显式 `return`，无返回值的**不写**裸 `return`。
- **跨层契约用 Protocol**：`framework/contracts.py`，不靠隐式鸭子类型。
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

`flaskServer.exe`（PyInstaller 打包的 PyQt5 GUI），`http://127.0.0.1:8787`。**重启电脑后要手动双击 exe 并点窗口里的「启动服务」**，光开窗口服务不会自己起。账号 `test01` / `admin123`。

**鉴权用 token，不是 cookie**：登录响应返回 `token`，后续请求把它当**表单参数**传（不是放 header）；缺/错 token → `9001 新增失败，参数缺失或token失效`。

## 排查顺序

- 用例没跑 / 数量不对 → 先 `--collect-only -q`（十有八九是命名不匹配、参数化没对上，或被 `norecursedirs` 排掉了）
- `ModuleNotFoundError` → 先想 `-m` vs 直接跑文件
- 整个 session 一条都不跑 → 看是不是有别的测试目录被收进来报 `collection error`
- 改了 `framework/` 后行为不对 → 确认改的是哪一层，别把测试专属逻辑塞进 `client`
- `${...}` 报 `ContextError` → 变量池里没这个 key（没提取到 / 提取时的 key 名对不上），去文件日志 `logs/app.log` 看提取那几行
- 数据库/接口断言"看起来过了但没验到" → 注意 `contains` 是**精确等值**匹配（不是子串），yaml 里要写完整消息
- 跨用例关联在 `-n` 下失效 → 变量池是进程内的，有依赖的用例集别开 `-n`
- **日志看不见了** → 两条路查：① logger 不能设 `propagate = False`（会切断 pytest 挂 root 的日志捕获）；② 默认不加 `-s`，日志只在用例失败时以 `Captured log` 形式出现，要看实时就加 `-s`
- 控制台输出挤成一团 → 检查 `addopts` 里有没有 `-s`（有的话日志会糊在 pytest 那行未结束的用例 id 后面）
