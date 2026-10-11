import pytest

from framework.config import Config
from framework.context.context import Context
from framework.exception.errors import ConfigError, ContextError

RAW = {
    "base_url": "http://127.0.0.1:8787",
    "http": {"timeout": 10},
    "login": {"username": "test01", "password": "admin123"},
}

# 单测专用配置文件（内容与 RAW 一致，但走的是真实的「读文件」那条路）
FIXTURE_CONFIG = "tests/data/config.yaml"


class TestConfig:
    """取值行为：点号路径、类型、缺 key。"""

    def test_dot_path(self) -> None:
        cfg = Config(RAW)
        assert cfg.get("login.username") == "test01"
        assert cfg.get("http.timeout") == 10

    def test_top_level_key(self) -> None:
        cfg = Config(RAW)
        assert cfg.get("base_url") == "http://127.0.0.1:8787"

    def test_middle_layer_whole_dict(self) -> None:
        """中间层能整块取出来（与 Context 行为一致）。"""
        cfg = Config(RAW)
        assert cfg.get("login") == {"username": "test01", "password": "admin123"}

    def test_type_preserved(self) -> None:
        cfg = Config(RAW)
        assert isinstance(cfg.get("http.timeout"), int)

    def test_missing_key_raises_not_none(self) -> None:
        cfg = Config(RAW)
        with pytest.raises(ContextError):
            cfg.get("nope")

    def test_exists(self) -> None:
        cfg = Config(RAW)
        assert cfg.exists("login.password")
        assert not cfg.exists("nope")

    def test_load_missing_file_raises_config_error(self) -> None:
        with pytest.raises(ConfigError):
            Config.load("config/does_not_exist.yaml")


class TestEnvOverlay:
    """环境变量覆盖。

    用 load() 的 environ 参数注入，**不去改 os.environ**（那会污染别的测试）。

    配置读的是 tests/data/config.yaml（**单测专用**）—— 不是生产的 config/config.yaml。
    读生产的那份会让「改一下配置」把单测带崩（断言绑在真实值上），
    「框架单测零依赖」就成了空话。
    """

    def test_overrides_file_value(self) -> None:
        cfg = Config.load(FIXTURE_CONFIG, environ={"APP_LOGIN__PASSWORD": "hacked"})
        assert cfg.get("login.password") == "hacked"

    def test_cast_follows_existing_type(self) -> None:
        """配置里 timeout 是 int，覆盖后必须还是 int —— 否则 "30" 会一路传进 requests。"""
        cfg = Config.load(FIXTURE_CONFIG, environ={"APP_HTTP__TIMEOUT": "30"})
        assert cfg.get("http.timeout") == 30
        assert isinstance(cfg.get("http.timeout"), int)

    def test_single_underscore_is_part_of_key(self) -> None:
        """base_url 里的下划线是 key 的一部分，不是层级分隔符。"""
        cfg = Config.load(FIXTURE_CONFIG, environ={"APP_BASE_URL": "http://example.com"})
        assert cfg.get("base_url") == "http://example.com"

    def test_new_key_stays_string(self) -> None:
        """环境变量新加的 key 没有原值可参照，保持字符串。"""
        cfg = Config.load(FIXTURE_CONFIG, environ={"APP_EXTRA__TOKEN": "abc"})
        assert cfg.get("extra.token") == "abc"

    def test_other_env_vars_ignored(self) -> None:
        """没有 APP_ 前缀的一律不看 —— 系统里变量海了去了。"""
        cfg = Config.load(FIXTURE_CONFIG, environ={"PATH": "/usr/bin", "LOGIN__PASSWORD": "x"})
        assert cfg.get("login.password") == "admin123"

    def test_bad_number_raises(self) -> None:
        """数字类型覆盖时值不合法要喊出来，不能静默塞个字符串进去。"""
        with pytest.raises(ConfigError):
            Config.load(FIXTURE_CONFIG, environ={"APP_HTTP__TIMEOUT": "abc"})


class TestAsContextParent:
    """Config 当 Context 的父级 —— 这是它在框架里的真实用法。"""

    def test_both_layers_reachable(self) -> None:
        ctx = Context(parent=Config(RAW))
        ctx.set("token", "jwt-abc")

        assert ctx.get("login.username") == "test01"  # 落到配置层
        assert ctx.get("token") == "jwt-abc"  # 走变量层

    def test_context_cannot_reach_config_layer(self) -> None:
        """用例 set 同名 key 只写自己层，配置层纹丝不动。"""
        parent = Config(RAW)
        ctx = Context(parent=parent)
        ctx.set("login.username", "attacker")

        assert ctx.get("login.username") == "attacker"
        assert parent.get("login.username") == "test01"
