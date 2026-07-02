import os

import pytest
from unittest.mock import patch, MagicMock

from core.env_manager import EnvManager, get_env_manager, reset_env_manager, ENV_VAR_NAME
from core.runner import SessionRunner
from core.client import HttpSession
from core.step import Step


@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前后重置 EnvManager 单例，避免环境变量污染"""
    reset_env_manager()
    yield
    reset_env_manager()


# ---------- EnvManager 基础功能 ----------

class TestEnvManager:
    """环境管理器核心功能测试"""

    def test_load_default_env(self):
        """未设置 TEST_ENV 时使用 env.yml 的 default（dev）"""
        # 确保环境变量未设置
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ENV_VAR_NAME, None)
            mgr = EnvManager()
        assert mgr.current_env == "dev"
        assert mgr.base_url == "https://dev-api.example.com"

    def test_switch_by_env_var(self):
        """通过 TEST_ENV 环境变量切换到 qa"""
        with patch.dict(os.environ, {ENV_VAR_NAME: "qa"}):
            mgr = EnvManager()
        assert mgr.current_env == "qa"
        assert mgr.base_url == "https://qa-api.example.com"

    def test_switch_by_param(self):
        """参数传入优先级最高，覆盖环境变量"""
        with patch.dict(os.environ, {ENV_VAR_NAME: "qa"}):
            mgr = EnvManager(env_name="prod")
        assert mgr.current_env == "prod"
        assert mgr.base_url == "https://api.example.com"

    def test_switch_at_runtime(self):
        """运行时切换环境"""
        mgr = EnvManager()
        assert mgr.current_env == "dev"
        mgr.switch_env("prod")
        assert mgr.current_env == "prod"
        assert mgr.base_url == "https://api.example.com"

    def test_invalid_env_raises(self):
        """切换到不存在的环境应报错"""
        mgr = EnvManager()
        with pytest.raises(ValueError, match="不存在"):
            mgr.switch_env("staging")

    def test_available_envs(self):
        """列出所有可用环境"""
        mgr = EnvManager()
        assert set(mgr.available_envs) == {"dev", "qa", "prod"}

    def test_invalid_env_file(self):
        """env.yml 不存在应报错"""
        with pytest.raises(FileNotFoundError):
            EnvManager(env_file="nonexistent.yml")


# ---------- 点号路径配置读取 ----------

class TestEnvConfigAccess:
    """配置项读取测试"""

    def test_get_db_host(self):
        """点号路径读取嵌套配置：db.host"""
        mgr = EnvManager(env_name="dev")
        assert mgr.get("db.host") == "127.0.0.1"
        assert mgr.get("db.port") == 3306
        assert mgr.get("db.database") == "api_test_dev"

    def test_get_db_config_dict(self):
        """获取完整 db 配置字典"""
        mgr = EnvManager(env_name="qa")
        db = mgr.db_config
        assert db["host"] == "192.168.1.100"
        assert db["database"] == "api_test_qa"

    def test_get_nonexistent_key_returns_default(self):
        """不存在的 key 返回默认值"""
        mgr = EnvManager(env_name="dev")
        assert mgr.get("nonexistent.key", "fallback") == "fallback"

    def test_get_redis_config(self):
        """读取 redis 配置"""
        mgr = EnvManager(env_name="prod")
        assert mgr.get("redis.host") == "10.0.1.101"
        assert mgr.get("redis.db") == 2


# ---------- Runner 集成 ----------

class TestRunnerEnvIntegration:
    """SessionRunner 与环境管理集成测试"""

    def test_runner_auto_injects_base_url(self):
        """config 未设置 base_url 时自动从当前环境注入"""
        from httprunner.models import TConfig

        mgr = get_env_manager()
        mgr.switch_env("qa")

        runner = SessionRunner()
        # 构造一个 base_url 为空的 config
        runner.config = TConfig(name="env用例", base_url="", variables={})
        # 应被注入为 qa 环境的 base_url
        assert runner.config.base_url == "https://qa-api.example.com"

    def test_runner_keeps_explicit_base_url(self):
        """config 显式设置了 base_url 时不被覆盖"""
        from httprunner.models import TConfig

        mgr = get_env_manager()
        mgr.switch_env("dev")

        runner = SessionRunner()
        runner.config = TConfig(name="env用例", base_url="https://custom.example.com", variables={})
        # 显式设置的 base_url 应保留
        assert runner.config.base_url == "https://custom.example.com"

    def test_step_uses_env_base_url(self):
        """Step 中相对 URL 拼接环境 base_url（端到端验证，mock 网络）"""
        from httprunner.models import TConfig

        mgr = get_env_manager()
        mgr.switch_env("prod")

        runner = SessionRunner()
        runner.config = TConfig(name="env用例", base_url="", variables={})
        runner.session_variables = {}

        step = Step(
            name="相对路径请求",
            request={"url": "/users/123", "method": "GET"},
            validate=[{"check": "status_code", "assert_type": "eq", "expect": 200}],
        )

        captured = {}

        def fake_request(self, method, url, **kwargs):
            captured["url"] = url
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {}
            resp.headers = {}
            return resp

        with patch.object(HttpSession, "request", new=fake_request):
            result = step.run(runner)

        assert result["success"] is True
        # 相对路径应被拼接为 prod 环境的 base_url
        assert captured["url"] == "https://api.example.com/users/123"

    def test_switch_env_changes_base_url(self):
        """切换环境后，新创建的 runner 使用新的 base_url"""
        from httprunner.models import TConfig

        mgr = get_env_manager()

        # dev 环境
        mgr.switch_env("dev")
        runner1 = SessionRunner()
        runner1.config = TConfig(name="dev用例", base_url="", variables={})
        assert runner1.config.base_url == "https://dev-api.example.com"

        # 切换到 prod
        mgr.switch_env("prod")
        runner2 = SessionRunner()
        runner2.config = TConfig(name="prod用例", base_url="", variables={})
        assert runner2.config.base_url == "https://api.example.com"


# ---------- 单例管理 ----------

class TestSingleton:
    """全局单例测试"""

    def test_singleton_is_shared(self):
        """get_env_manager 返回同一实例"""
        mgr1 = get_env_manager()
        mgr2 = get_env_manager()
        assert mgr1 is mgr2

    def test_reset_creates_new_instance(self):
        """reset 后获取新实例"""
        mgr1 = get_env_manager()
        reset_env_manager()
        mgr2 = get_env_manager()
        assert mgr1 is not mgr2
