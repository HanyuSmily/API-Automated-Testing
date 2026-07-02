import time
from typing import Dict, List
from loguru import logger
from core.client import HttpSession
from core.env_manager import get_env_manager
from core.loader import load_debugtalk, get_project_root
from core.parser import Parser
from core.step import Step
from utils.assert_utils import AssertUtils


class SessionRunner:
    """测试会话运行器：负责调度和执行测试用例的核心类"""

    def __init__(self, project_meta=None):
        """初始化会话运行器

        Args:
            project_meta: 项目元数据对象，包含调试函数等信息；
                          为 None 时自动从项目根目录加载 debugtalk.py
        """
        # 创建 HTTP 会话对象，用于发送请求
        self.session = HttpSession()
        # 若未传入 project_meta，自动加载 debugtalk.py 中的自定义函数
        if project_meta is None:
            project_root = get_project_root()
            project_meta = load_debugtalk(project_root)
        # 从项目元数据中提取自定义函数，若无则使用空字典
        functions = project_meta.functions if project_meta else {}
        # 创建变量解析器，用于解析请求中的变量占位符与 ${func()} 调用
        self.parser = Parser(functions)
        # 存储所有步骤的执行结果
        self.results = []
        # 存储会话级别的变量（跨步骤共享）
        self.session_variables = {}
        # 测试配置对象（包含基础URL、变量等）
        self._config = None
        # 测试步骤列表
        self._teststeps = []
        # 测试开始时间戳
        self._start_at = 0
        # 测试总耗时（秒）
        self._duration = 0
        # 测试用例ID
        self.case_id = ""

    @property
    def config(self):
        """获取测试配置对象"""
        return self._config

    @config.setter
    def config(self, value):
        """设置测试配置对象，自动注入当前环境的 base_url

        若 config 未指定 base_url，则从 EnvManager 读取当前环境的 base_url 补全，
        实现「一键切换环境」：只需切换 TEST_ENV，所有用例的 base_url 随之生效。
        """
        self._config = value
        if value is not None:
            current_base = getattr(value, "base_url", "") or ""
            if not current_base:
                try:
                    env_base = get_env_manager().base_url
                    if env_base:
                        value.base_url = env_base
                        logger.debug(f"自动注入 base_url: {env_base} (来自当前环境)")
                except Exception as e:
                    logger.debug(f"加载环境 base_url 失败，跳过注入: {e}")

    @property
    def teststeps(self):
        """获取测试步骤列表"""
        return self._teststeps

    @teststeps.setter
    def teststeps(self, value):
        """设置测试步骤列表"""
        self._teststeps = value

    def test_start(self, param: Dict = None) -> "SessionRunner":
        """测试入口方法，由 pytest 自动发现并调用

        Args:
            param: 可选参数，用于传递额外参数

        Returns:
            SessionRunner: 返回自身实例，支持链式调用
        """
        # 解析配置信息（如变量、用例ID等）
        self._parse_config(param)

        # 记录测试开始日志，包含用例名称和用例ID
        logger.info(
            f"Start to run testcase: {self._config.name}, TestCase ID: {self.case_id}"
        )

        # 记录测试开始时间戳
        self._start_at = time.time()
        try:
            # 遍历所有测试步骤并执行
            for step in self.teststeps:
                self._run_step(step)
        finally:
            # 计算测试总耗时（无论成功或失败都会执行）
            self._duration = time.time() - self._start_at
        # 返回自身实例，支持链式调用
        return self

    def _parse_config(self, param):
        """解析测试配置

        Args:
            param: 可选参数
        """
        # 检查配置对象是否存在
        if self._config:
            # 从配置中获取用例ID，若无则使用空字符串
            self.case_id = getattr(self._config, "case_id", "")
            # 检查配置中是否包含变量
            if hasattr(self._config, "variables"):
                # 将配置中的变量赋值给会话变量
                self.session_variables = self._config.variables

    def _run_step(self, step):
        """执行单个测试步骤（内部方法，处理字典格式的步骤）

        Args:
            step: 字典格式的测试步骤

        Returns:
            dict: 步骤执行结果
        """
        # 记录步骤开始日志
        logger.info(f"正在准备调度步骤: {step.get('name', '')}")

        # 将字典格式的步骤转换为 Step 对象
        step_obj = Step(
            name=step.get("name", ""),          # 步骤名称
            request=step.get("request", {}),     # 请求配置
            validate=step.get("validate", [])    # 断言列表
        )

        # 调用 Step 对象的 run 方法执行步骤，传入当前 runner 作为上下文
        step_result = step_obj.run(self)
        # 将步骤结果添加到结果列表中
        self.results.append(step_result)
        # 返回步骤执行结果
        return step_result

    def run_step(self, step):
        """执行单个测试步骤（公开方法，处理 Step 对象）

        Args:
            step: Step 对象格式的测试步骤

        Returns:
            dict: 步骤执行结果
        """
        # 记录步骤开始日志
        logger.info(f"正在准备调度步骤: {step.name}")
        # 调用 Step 对象的 run 方法执行步骤
        step_result = step.run(self)
        # 将步骤结果添加到结果列表中
        self.results.append(step_result)
        # 返回步骤执行结果
        return step_result

    def run_testcase(self, testcase):
        """执行完整的测试用例

        Args:
            testcase: 测试用例对象（包含 config 和 teststeps）

        Returns:
            list: 所有步骤的执行结果列表
        """
        # 记录测试用例开始日志
        logger.info(f"开始执行测试用例: {testcase.config.name}")
        # 将用例配置中的变量赋值给会话变量
        self.session_variables = testcase.config.variables

        # 遍历所有测试步骤
        for step in testcase.teststeps:
            try:
                # 执行单个步骤
                self.run_step(step)
            except Exception as e:
                # 记录步骤执行失败日志
                logger.error(f"步骤 {step.name} 执行失败: {e}")
                # 遇到错误时停止执行后续步骤
                break

        # 记录测试用例执行完毕日志
        logger.info("测试用例执行完毕")
        # 返回所有步骤的执行结果
        return self.results

    def get_summary(self):
        """获取测试执行摘要

        Returns:
            object: 包含 success（是否全部通过）、results（步骤结果列表）、duration（总耗时）的对象
        """
        # 判断所有步骤是否都执行成功
        success = all(r.get("success", False) for r in self.results)
        # 动态创建 Summary 对象并返回
        return type('Summary', (), {
            'success': success,    # 测试是否全部通过
            'results': self.results,  # 所有步骤的执行结果
            'duration': self._duration  # 测试总耗时（秒）
        })()