import os
from typing import Any, Dict, Text

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
    """

    def __init__(self, env_file: Text = None, env_name: Text = None, project_root: Text = None):
        """初始化环境管理器

        Args:
            env_file: env.yml 路径，默认为项目根目录下的 env.yml
            env_name: 指定环境名（dev/qa/prod），优先级高于环境变量
            project_root: 项目根目录，默认自动探测
        """
        # 定位 env.yml
        if env_file is None:
            root = project_root or get_project_root()
            env_file = os.path.join(root, "env.yml")
        self.env_file = env_file

        # 加载配置
        self._raw = self._load_yaml(env_file)

        # 确定当前环境
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
        if env_name: #构造时显式传入 env_name
            self._env_source = "参数传入"
            return env_name
        env_from_var = os.environ.get(ENV_VAR_NAME) #环境变量 TEST_ENV
        if env_from_var:
            self._env_source = f"环境变量 {ENV_VAR_NAME}"
            return env_from_var
        default_env = self._raw.get("default") #env.yml 中的 default 字段
        if default_env:
            self._env_source = "env.yml default"
            return default_env
        raise ValueError(f"无法确定测试环境：未传入 env_name，{ENV_VAR_NAME} 未设置，env.yml 也无 default")

    def get_env_config(self, env_name: Text = None) -> Dict[Text, Any]:
        """获取指定环境的完整配置，默认返回当前环境

        Args:
            env_name: 环境名，为 None 时返回当前环境
        """
        target = env_name or self._current_env #默认返回当前环境
        envs = self._raw["environments"] #env.yml 中的 environments 字段
        if target not in envs:
            available = list(envs.keys()) #env.yml 中的 environments 字段的键值对
            raise ValueError(f"环境 '{target}' 不存在，可用环境: {available}")
        return envs[target] #返回指定环境的配置

    def get(self, key: Text, default: Any = None) -> Any:
        """获取当前环境下指定配置项（支持点号路径，如 'db.host'）"""
        config = self.get_env_config() #获取当前环境的配置
        current = config
        for segment in key.split("."):
            if not isinstance(current, dict) or segment not in current: #如果当前值不是字典或键不存在
                return default
            current = current[segment]
        return current

    @property
    def base_url(self) -> Text:
        """便捷属性：当前环境的 base_url"""
        url = self.get("base_url", "") #获取当前环境的 base_url
        if not url:
            logger.warning(f"当前环境 {self._current_env} 未配置 base_url")
        return url

    @property
    def db_config(self) -> Dict[Text, Any]:
        """便捷属性：当前环境的数据库配置"""
        return self.get("db", {}) or {} #获取当前环境的数据库配置



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
