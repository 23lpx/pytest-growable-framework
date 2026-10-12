"""测试报告：对 allure 的薄封装。

为什么要包这一层：要在报告里写「步骤」，`ScenarioRunner` 就得认识 allure ——
这是**框架核心第一次依赖一个外部工具**。把耦合收在这一个文件里：
将来换 pytest-html / 别的报告，只改这里，runner 一个字不动。
"""

from contextlib import contextmanager
from typing import Iterator

import allure


@contextmanager
def step(title: str) -> Iterator[None]:
    """报告里的一个步骤，用法：

        with report.step("登录"):
            ...

    没有 allure 运行上下文时（比如直接 import 跑框架单测）照样能调用 ——
    allure 自己会把记录丢掉，不用这里判断。
    """
    with allure.step(title):
        yield
