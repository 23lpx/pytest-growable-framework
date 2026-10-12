class ValidationOp:
    """校验操作符 —— 即 yaml 里 validation 每条规则的 key。

    禁止在代码里裸写这些字符串（魔法值），一律引用这里。
    """

    CONTAINS = "contains"
