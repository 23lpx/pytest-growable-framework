class FrameworkError(Exception):
    """框架所有异常的基类。

    统一类型，方便上层一把捞；带一个简易的 context，供上层补充执行上下文
    （比如 Runner 补 case_name），异常往上抛时上下文一路带着，方便定位。
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.context: list[str] = []

    def add_context(self, item: str) -> None:
        """补充一条执行上下文，由上层调用（如 Runner 补 case_name）。"""
        self.context.append(item)

    def __str__(self) -> str:
        message = super().__str__()
        if self.context:
            return f"{message} [{'; '.join(self.context)}]"
        return message
