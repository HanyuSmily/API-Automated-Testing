"""报告生成验证测试

验证 pytest-html 报告和 allure 数据能正确生成，且失败用例的 loguru 日志被捕获。
"""
import os

import pytest
from loguru import logger

from core.env_manager import get_env_manager

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
HTML_REPORT = os.path.join(REPORTS_DIR, "report.html")
ALLURE_DATA_DIR = os.path.join(REPORTS_DIR, "allure_data")


class TestReportGeneration:
    """验证报告文件生成"""

    def test_html_report_exists(self):
        """HTML 报告文件存在且非空"""
        assert os.path.isfile(HTML_REPORT), "report.html 不存在"
        assert os.path.getsize(HTML_REPORT) > 0, "report.html 为空"

    def test_allure_data_exists(self):
        """Allure 原始数据目录存在且包含文件"""
        assert os.path.isdir(ALLURE_DATA_DIR), "allure_data 目录不存在"
        files = os.listdir(ALLURE_DATA_DIR)
        assert len(files) > 0, "allure_data 目录为空"

    def test_allure_environment_properties(self):
        """Allure environment.properties 包含环境信息"""
        env_path = os.path.join(ALLURE_DATA_DIR, "environment.properties")
        assert os.path.isfile(env_path), "environment.properties 不存在"
        content = open(env_path, "r", encoding="utf-8").read()
        assert "Test.Env=" in content
        assert "Base.URL=" in content


class TestEnvironmentInReport:
    """验证环境信息被注入报告"""

    def test_env_manager_loaded(self):
        """EnvManager 单例可正常加载"""
        mgr = get_env_manager()
        assert mgr.current_env in ("dev", "qa", "prod")
        assert mgr.base_url.startswith("https://")

    def test_metadata_has_env(self, pytestconfig):
        """pytest metadata 包含测试环境"""
        metadata = getattr(pytestconfig, "_metadata", {})
        assert "测试环境" in metadata
        assert "Base URL" in metadata


class TestFailureLogCapture:
    """验证失败用例的 loguru 日志被捕获到报告"""

    @pytest.mark.xfail(reason="验证失败日志捕获机制，预期失败")
    def test_failure_logs_captured(self):
        """故意失败，验证 loguru 日志出现在报告 sections 中"""
        logger.info("这是一条失败前的日志，应出现在报告中")
        logger.warning("这是一条警告日志")
        # 故意断言失败
        assert False, "故意失败以验证日志捕获"

    def test_success_no_extra_logs(self):
        """成功用例不应触发日志附加（但仍正常运行）"""
        logger.info("成功用例的日志")
        assert True
