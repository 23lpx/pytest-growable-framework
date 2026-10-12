class EnvVar:
    """环境变量覆盖配置的命名约定。

    APP_LOGIN__PASSWORD  ->  login.password
    APP_BASE_URL         ->  base_url

    层级只认**双下划线** —— 单下划线是 key 本身的一部分（base_url），
    拿它当分隔符会把 base_url 拆成 base.url，认不出来。
    """

    PREFIX = "APP_"
    LEVEL = "__"


class ConfigFile:
    """配置文件位置（相对项目根，与 YamlRead 的约定一致）。"""

    DEFAULT_PATH = "config/config.yaml"
