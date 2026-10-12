# 归档区

**这里的东西不再维护，pytest 也收不到它**（`pytest.ini` 的 `testpaths = cases`，不指向这里）。
保留是为了「将来想查当年怎么做的」—— **需要时看，别拿来跑**。

---

## flaskServer（2026-10-12 归档）

**研发期的测试靶场**，已被第二个被测系统（**商用短链平台**）取代。

### 为什么归档

它是**纯内存 mock、没有任何数据库**（2026-10-11 用 MySQL `general_log` 实测确认）。
拿它练框架的头几步很合适 —— 接口简单、跑得快、不用起中间件。但**它能教的东西已经教完了**：

| 框架能力 | flaskServer 能教吗 |
|---|---|
| 数据驱动（yaml 拆用例） | ✅ 能 |
| 接口关联（`${}` + `extract`） | ✅ 能 |
| **查库校验** | ❌ **教不了** —— 它没库 |

`data/api/db_check_cases.yaml` 就是被卡在这儿的产物：**接口打 flaskServer、库查 docker 的 demo**，两边数据各准备各的 —— 是**链路演示**，不是真用例。

真靶子（短链平台，真库真接口）来了之后，它就从"练手"变成了"包袱"：
**保留它 = 每次跑测试都得先双击一个 exe、还得维护它那 30 条用例**，而收益是零。

### 归档了什么

```
flaskServer/
├── data/api/          9 个接口用例 yaml（用户 CRUD + 电商 3 个 + db_check）
├── data/scenarios/    1 个电商下单场景（登录→列表→详情→下单→支付）
└── cases/             两个 pytest 入口（test_api / test_scenario）+ test_/（更早的备份）
```

### 还有参考价值的部分

**`data/api/db_check_cases.yaml`** —— 它演示了 yaml 的 `db:` 段怎么写：

```yaml
db:
  - table: user                    # 查哪张表
    where: {user_id: "${user_id}"} # 什么条件（值可引变量）
    expect: {username: test01}     # 期望什么
```

**声明式，不写 SQL** —— SQL 由 `adapters/db_checker.py` 生成（表名过反引号 + 正则校验，值走参数化）。
短链平台将来接上库权限后，可以照这个模子写。

> 相关的框架代码**还在**（`adapters/db_checker.py` / `ports/query.py` / `infrastructure/db.py`），
> 只是暂时没有用例在用 —— 等短链平台开了只读库权限就会用上。
