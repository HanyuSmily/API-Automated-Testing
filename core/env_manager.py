import os
from typing import Any, Dict, Text, Optional

import yaml
from loguru import logger

from core.loader import get_project_root


# env.yml 中通过此环境变量指定当前环境
ENV_VAR_NAME = "TEST_ENV"


class EnvManager:
    """环境管理器：加载 env.yml 并提供当前环境的配置访问

    切换环境的方式（优先级从高到低）:
        1. 构造时显式传入 env_name
        2. 环境变量 TEST_ENV
        3. env.yml 中的 default 字段

    配置层级：global 全局配置 -> environments 环境级配置（后者覆盖前者）
    """

    def __init__(self, env_file: Text = None, env_name: Text = None, project_root: Text = None):
        """初始化环境管理器

        Args:
            env_file: env.yml 路径，默认为项目根目录下的 env.yml
            env_name: 指定环境名（mock/dev/qa/prod），优先级高于环境变量
            project_root: 项目根目录，默认自动探测
        """
        if env_file is None:
            root = project_root or get_project_root()
            env_file = os.path.join(root, "env.yml")
        self.env_file = env_file

        self._raw = self._load_yaml(env_file)
        self._global_config = self._raw.get("global", {}) or {}

        self._current_env = self._resolve_env(env_name)
        logger.info(f"当前测试环境: {self._current_env} (来源: {self._env_source})")

    @staticmethod
    def _load_yaml(env_file: Text) -> Dict[Text, Any]:
        """读取并解析 env.yml"""
        if not os.path.isfile(env_file):
            raise FileNotFoundError(f"环境配置文件不存在: {env_file}")
        with open(env_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or "environments" not in data:
            raise ValueError(f"env.yml 格式错误，缺少 environments 字段: {env_file}")
        return data

    def _resolve_env(self, env_name: Text = None) -> Text:
        """按优先级确定当前环境名，并记录来源"""
        if env_name:
            self._env_source = "参数传入"
            return env_name
        env_from_var = os.environ.get(ENV_VAR_NAME)
        if env_from_var:
            self._env_source = f"环境变量 {ENV_VAR_NAME}"
            return env_from_var
        default_env = self._raw.get("default")
        if default_env:
            self._env_source = "env.yml default"
            return default_env
        raise ValueError(f"无法确定测试环境：未传入 env_name，{ENV_VAR_NAME} 未设置，env.yml 也无 default")

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并两个字典，override 覆盖 base"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_env_config(self, env_name: Text = None) -> Dict[Text, Any]:
        """获取指定环境的完整配置（已合并 global 全局配置），默认返回当前环境

        Args:
            env_name: 环境名，为 None 时返回当前环境
        """
        target = env_name or self._current_env
        envs = self._raw["environments"]
        if target not in envs:
            available = list(envs.keys())
            raise ValueError(f"环境 '{target}' 不存在，可用环境: {available}")
        env_config = envs[target] or {}
        return self._deep_merge(self._global_config, env_config)

    def get(self, key: Text, default: Any = None) -> Any:
        """获取当前环境下指定配置项（支持点号路径，如 'db.host'、'accounts.admin.username'）"""
        config = self.get_env_config()
        current = config
        for segment in key.split("."):
            if not isinstance(current, dict) or segment not in current:
                return default
            current = current[segment]
        return current

    # ============================================================
    # 便捷属性
    # ============================================================

    @property
    def base_url(self) -> Text:
        """当前环境的 base_url"""
        url = self.get("base_url", "")
        if not url:
            logger.warning(f"当前环境 {self._current_env} 未配置 base_url")
        return url

    @property
    def db_config(self) -> Dict[Text, Any]:
        """当前环境的数据库配置"""
        return self.get("db", {}) or {}

    @property
    def redis_config(self) -> Dict[Text, Any]:
        """当前环境的 Redis 配置"""
        return self.get("redis", {}) or {}

    @property
    def accounts(self) -> Dict[Text, Any]:
        """当前环境的所有测试账号"""
        return self.get("accounts", {}) or {}

    def get_account(self, account_type: Text = "member") -> Dict[Text, Any]:
        """获取指定类型的测试账号

        Args:
            account_type: 账号类型，如 'admin'、'member'

        Returns:
            {"username": xxx, "password": xxx}
        """
        account = self.get(f"accounts.{account_type}", {})
        if not account:
            logger.warning(f"当前环境 {self._current_env} 未配置 {account_type} 账号")
        return account or {}

    @property
    def admin_account(self) -> Dict[Text, Any]:
        """管理员账号"""
        return self.get_account("admin")

    @property
    def member_account(self) -> Dict[Text, Any]:
        """会员账号"""
        return self.get_account("member")

    @property
    def request_timeout(self) -> int:
        """请求超时时间（秒）"""
        return self.get("request_timeout", 30)

    @property
    def retry_config(self) -> Dict[Text, Any]:
        """重试配置"""
        return self.get("retry", {}) or {}

    @property
    def report_config(self) -> Dict[Text, Any]:
        """报告配置"""
        return self.get("report", {}) or {}

    # ============================================================
    # 环境切换与查询
    # ============================================================

    @property
    def current_env(self) -> Text:
        """当前环境名"""
        return self._current_env

    @property
    def available_envs(self):
        """所有可用环境名"""
        return list(self._raw["environments"].keys())

    def switch_env(self, env_name: Text):
        """运行时切换当前环境"""
        if env_name not in self._raw["environments"]:
            available = list(self._raw["environments"].keys())
            raise ValueError(f"无法切换到不存在的环境 '{env_name}'，可用环境: {available}")
        old = self._current_env
        self._current_env = env_name
        self._env_source = "运行时切换"
        logger.info(f"环境切换: {old} -> {env_name}")
        return self

    def is_mock_env(self) -> bool:
        """判断当前是否为 Mock 环境"""
        return self._current_env == "mock"


# ---------- 模块级单例，便于全局访问 ----------

_singleton = None


def get_env_manager() -> EnvManager:
    """获取全局 EnvManager 单例（首次调用时初始化）"""
    global _singleton
    if _singleton is None:
        _singleton = EnvManager()
    return _singleton


def reset_env_manager():
    """重置单例（测试场景：切换 env.yml 后需重新加载）"""
    global _singleton
    _singleton = None
