# 接口自动化（pytest + 自研框架）

用 pytest 做执行底座 + 一套自研的**分层数据驱动**框架，对商用短链平台（Java / Spring Cloud，经网关）做接口自动化。

**特点**

- **数据驱动** —— 单接口和场景都是 yaml，**加数据文件 = 加用例**，代码不用改
- **单向分层** —— 由内到外 `entities → ports → usecases → adapters → infrastructure`，内层只认端口、不认实现
- **两种消费方式，一个执行器** —— 单接口展平成 N 个 pytest 节点（保住 `-k` / 重跑粒度），场景收成 1 个节点（顺序由数据决定）
- **可反复跑** —— 会话前后各记一份数据快照，跑完按差集自动清理；用例集能回归，不是一次性脚本
- **冒烟 / 回归分层** —— `-m smoke` 只跑 7 条核心路径（登录 / 鉴权 / 分组 / 查询），几秒出结果；200+ 条全量留给回归。标记写在 YAML 里，和 `xfail` 同一套机制

---

## 快速开始

环境：Python 3.12。（以下命令按 Windows 写；Linux / macOS 把 `Scripts/python.exe` 换成 `bin/python`。）

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt     # 装依赖 + 可编辑安装本包
cp config/config.example.yaml config/config.yaml                  # 填被测地址 / 测试账号
./.venv/Scripts/python.exe -m pytest                              # 跑接口用例
```

> `config/config.yaml` **不入库**（里面有测试账号和库密码），仓库只放占位符模板 `config.example.yaml`。
> 真值也可以完全不落文件，用环境变量注入：`APP_SHORTLINK__PWD=xxx`（`APP_` 前缀 + 双下划线分层）。

被测接口的约定：**成功判据是 `code=0`**（业务失败也是 HTTP 200，只看响应体）；token 放**请求头**。

---

## 项目结构

```
src/pytest_framework/     框架本体（按架构层分目录）
├── entities/             最内：用例模型 / 变量池 / 契约 / 异常 / 常量（零第三方依赖）
├── ports/                端口：sender / query（内层定契约，外层实现）
├── usecases/             编排：case_runner（单条）/ scenario_runner（场景）/ 校验 / 提取
├── adapters/             适配：请求 / 查库 / 读 yaml / 配置（跨边界的格式转换）
└── infrastructure/       最外：http / logging（含脱敏）/ db / report(allure) / path

cases/                    测试入口（加数据文件 = 加用例）
data/api_shortlink/*.yaml 单接口用例
data/scenarios/*.yaml     业务场景
config/                   环境配置（config.yaml 不入库）
conftest.py               Composition Root：fixture + 初始化
```

---

## 用例怎么写

**单接口** —— 一个接口一个 yaml，根节点是 dict：

```yaml
base_info:
  api_name: group-add
  url: '/link-server/api/group/v1/add'
  method: POST
  headers: { 'Content-Type': 'application/json' }

test_cases:
  - case_name: "创建分组：正常创建"
    headers: { token: "${token}" }
    data: { title: "g1_auto_${timestamp()}" }
    validation:
      - contains: { code: 0 }
```

一条用例能写的字段：`data`（请求参数）、`validation`（响应断言）、`extract`（提取进变量池，供后续 `${}` 引用）、`db`（查库断言）、`path_params`、`headers`（用例级，覆盖接口级）、`xfail`（已知缺陷标记）、`smoke`（冒烟标记）、`skip`（前置条件不具备，暂时跳过）。

**场景** —— 根节点是 list，**顺序即执行顺序**；把几个接口块顺序排开，用 `extract` + `${}` 在步骤间传值。

**逃生舱** —— 流程里有 if / 循环 / 等待的（如轮询等异步受理），直接写 Python 调 `CaseRunner`，见 `cases/test_shortlink_flow.py`。

> 判据：**流程线性的 → yaml；有 如果/循环/等待 → 代码**。

---

## 常用命令

```bash
./.venv/Scripts/python.exe -m pytest                    # 跑接口用例
./.venv/Scripts/python.exe -m pytest tests/             # 跑框架自身的单测（不依赖被测服务）
./.venv/Scripts/python.exe -m pytest --collect-only -q  # 只收集不执行
./.venv/Scripts/python.exe -m pytest -k 分组            # 按名字筛
./.venv/Scripts/python.exe -m pytest -m smoke           # 冒烟集（7 条核心路径）
./.venv/Scripts/python.exe -m pytest -x                 # 第一个失败就停
```

## 报告

用 allure：先出原始数据，再渲染成页面。

```bash
./.venv/Scripts/python.exe -m pytest --alluredir=reports/allure-results
./tools/allure-2.46.1/bin/allure.bat generate reports/allure-results -o reports/allure-report --clean
./tools/allure-2.46.1/bin/allure.bat open reports/allure-report
```

## CI

- **GitHub Actions** —— push / PR 跑 `tests/`（框架单测，零外部依赖），跑完发钉钉 / 邮件
- **Jenkins** —— 跑 `cases/`（接口用例要连内网测试环境，GitHub 的 runner 够不着）
