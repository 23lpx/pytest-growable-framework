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

自研框架，按「数据 → 模型 → 适配 → pytest → runner」**单向分层**。

```
data/*.yaml
   │  reader/YamlRead.read
   ▼
model/CaseModel          封装：dict → 统一模型 {api, cases[]}
   │
   ▼
adapter/ExecuteCase      适配：模型 → 执行器契约（一条 = 一个 pytest 节点）
   │
   ▼
pytest 参数化             ← 多 case 调度权在 pytest 手里
   │  一次一条 case
   ▼
runner/CaseRunner.run(case)   编排，只三行
   ├── handler/RequestHandler     → client/HttpClient → 被测接口
   └── handler/ValidationHandler
```

| 模块 | 文件 | 职责 | 状态 |
|---|---|---|---|
| reader | `framework/reader/read_yaml.py` | 读文件 → dict | ✅ |
| model | `framework/model/case_model.py` | 封装 | ✅ |
| adapter | `framework/adapter/execute_case.py` | 适配（→ pytest.param） | ✅ |
| runner | `framework/runner/case_runner.py` | 编排单条用例 | ✅ |
| handler | `framework/handler/request_handler.py` | 发送请求 | ✅ |
| handler | `framework/handler/validation_handler.py` | 校验 | ✅ |
| handler | 提取（extract） | 动态数据提取 | ⬜ 待做（等 context） |
| client | `framework/client/http_client.py` | 通用 HTTP 底座 | ✅ |
| exception | `framework/exception/` | 异常体系 | ✅ |
| constants | `framework/constants/` | 常量（魔法值收口） | ✅ |
| contracts | `framework/contracts.py` | 跨层契约（Protocol） | ✅ |
| context | `framework/context/` | 动态数据 / 变量传递 | ⬜ 空 |
| config | `config/` | 配置（base_url / 账号 / 超时） | ⬜ 空（base_url 现硬编码在 conftest） |

**资源生命周期靠依赖注入**：`HttpClient` 由 `conftest` 的 `client` fixture（**session 级**，为连接复用）创建并 `close()`；`CaseRunner` / `RequestHandler` 只收不 new。整轮测试共用 1 条连接（不是每条用例一条）。

**文档**：`docs/代码规范.md`（写代码前看）、`docs/interface_test_framework_design_v2.md`、`docs/framework_exception_design_methodology.md`、`docs/修改方案.txt`

---

## 目录

| 目录 | 干什么 |
|---|---|
| `testcase/` | 测试用例（`test_login.py`）；`testcase/test_/` 是老用例备份，**pytest 不收**（`norecursedirs`） |
| `framework/` | 框架本体（见上表），只放活代码 |
| `data/` | 测试数据 yaml（`login_cases.yaml` / `add_user_cases.yaml`） |
| `docs/` | 设计文档 + 代码规范 |
| `archive/` | 归档：旧链路参考代码 + 被取代的旧设计文档 |
| `config/` | 配置（空，待做） |
| `logs/` | 日志（按天切） |
| `reports/` | 测试报告（allure，空） |
| `conftest.py` | `base_url` / `client` fixture + `init_logger()` |
| `pytest.ini` | pytest 配置 |

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
| 7 | config 收敛 + context/extract | ⬜ **下一步** |

---

## 命令速查

```bash
# 跑全部
./.venv/Scripts/python.exe -m pytest

# 只收集不执行（条数不对时第一件事）
./.venv/Scripts/python.exe -m pytest --collect-only -q

# 按名字筛 / 按标记筛
./.venv/Scripts/python.exe -m pytest -k login
./.venv/Scripts/python.exe -m pytest -m smoke
./.venv/Scripts/python.exe -m pytest -m "smoke or regression"

# 第一个失败就停
./.venv/Scripts/python.exe -m pytest -x

# 失败自动重跑
./.venv/Scripts/python.exe -m pytest --reruns 2 --reruns-delay 1

# 分布式（前提：用例之间互不依赖）
./.venv/Scripts/python.exe -m pytest -n 2

# 以「模块」方式跑单个文件（file 方式会找不到包）
./.venv/Scripts/python.exe -m framework.infra.logger
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

**⑤ 写文件别用裸相对路径** —— `open('logs/x')` 跟着 **cwd** 走，换目录跑就写错地方。统一用 `framework/infra/path.py` 的 `_project_root()`。

**⑥ `Path('D:/proj') / '/data/x'` 会顶掉项目根** —— 前导斜杠会让 pathlib 当成绝对路径，结果是 `D:\data\x` 而不是 `D:\proj\data\x`。写 `file_path` 前先 `lstrip("/\\")`。

**⑦ 循环导入** —— `model` 和 `adapter` 互相 import 过一次，直接 `ImportError: partially initialized module`。单向依赖 + 必要时局部 import。

**⑧ pytest 会递归收 `testpaths` 下的目录** —— `testcase/test_/` 这种备份目录也会被收进来，里面 import 断了就整个 `collection error`，**一条都不跑**。已在 `pytest.ini` 用 `norecursedirs = test_` 排除。

---

## 下一步

**配置收敛 + context/extract**：

1. `config/` —— 把散落的 `http://127.0.0.1:8787` / `test01/admin123` 收进配置，`conftest` 的 `base_url` 从配置读；
2. `framework/context/` + `handler/extract_handler.py` —— 动态数据提取（token / user_id），`Runner.run` 里那句 `# 3. 提取` 落地。

（再往后：allure 报告 —— 第 26 集。）
