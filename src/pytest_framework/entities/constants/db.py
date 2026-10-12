class DbKey:
    """DB 断言的键名 —— 即 yaml 里 `db:` 每条规则的 key。

    禁止在代码里裸写这些字符串（魔法值），一律引用这里。
    """

    TABLE = "table"
    WHERE = "where"
    EXPECT = "expect"
