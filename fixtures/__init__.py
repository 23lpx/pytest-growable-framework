"""Fixture 的**实现**（不是 fixture 声明）。

pytest 只认 conftest.py 和测试模块里的 `@pytest.fixture`，但**实现**可以放任意位置
—— 这个包就是用来承接「从 conftest 搬出来的逻辑」。

判据：**这段代码需要 pytest 吗？** 不需要 → 搬这儿来。
"""
