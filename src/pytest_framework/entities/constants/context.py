class Placeholder:
    """占位符语法常量。

    yaml 里 ${token} 引用变量、${today()} 调用函数 —— 区别只在「有没有括号」。
    """

    OPEN = "${"
    CLOSE = "}"


class PathSep:
    """变量池里多级 key 的分隔符，如 Cookie.access_token_cookie。"""

    DOT = "."
