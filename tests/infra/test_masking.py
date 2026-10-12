from pytest_framework.entities.constants.logging import MaskConfig
from pytest_framework.infrastructure.logging.masking import mask, mask_text


class TestMask:

    def test_sensitive_key_masked(self) -> None:
        assert mask({"passwd": "admin123"}) == {"passwd": MaskConfig.MASK}

    def test_key_is_kept(self) -> None:
        """只换值不删 key —— 删掉就丢掉了「这里本来有值」这个信息。"""
        assert "passwd" in mask({"passwd": "admin123"})

    def test_normal_value_untouched(self) -> None:
        assert mask({"user_name": "test01"}) == {"user_name": "test01"}

    def test_substring_match_case_insensitive(self) -> None:
        """access_token_cookie / phoneNumber 这类也要命中。"""
        assert mask({"access_token_cookie": "jwt"})["access_token_cookie"] == MaskConfig.MASK
        assert mask({"phoneNumber": "138"})["phoneNumber"] == MaskConfig.MASK

    def test_nested_dict(self) -> None:
        result = mask({"data": {"token": "abc", "msg": "ok"}})
        assert result == {"data": {"token": MaskConfig.MASK, "msg": "ok"}}

    def test_list(self) -> None:
        result = mask({"items": [{"passwd": "x"}, {"name": "y"}]})
        assert result == {"items": [{"passwd": MaskConfig.MASK}, {"name": "y"}]}

    def test_does_not_mutate_original(self) -> None:
        """脱敏是日志表现层的事，**绝不能碰真正要发出去的数据**。"""
        original = {"passwd": "admin123", "nested": {"token": "abc"}}
        masked = mask(original)

        assert masked == {"passwd": MaskConfig.MASK, "nested": {"token": MaskConfig.MASK}}
        assert original == {"passwd": "admin123", "nested": {"token": "abc"}}

    def test_non_dict_passthrough(self) -> None:
        assert mask("plain") == "plain"
        assert mask(200) == 200


class TestMaskText:

    def test_quoted_form(self) -> None:
        assert mask_text("'passwd': 'admin123'") == "'passwd': '***'"

    def test_equals_form(self) -> None:
        assert mask_text("passwd=admin123") == "passwd=***"

    def test_token_in_text(self) -> None:
        assert "9aBc" not in mask_text("token: 9aBc")

    def test_plain_text_untouched(self) -> None:
        assert mask_text("一切正常") == "一切正常"
