import io
import os
import sys
from datetime import datetime

import pytest
from loguru import logger


# ---------- 虚拟环境检查 ----------

def check_venv():
    """检查是否在虚拟环境中运行测试（CI 环境自动跳过）"""
    # CI 环境使用 Docker 镜像内的 Python，无需 .venv
    if os.environ.get("CI") or os.environ.get("GITLAB_CI"):
        return
    python_path = sys.executable
    if ".venv" not in python_path:
        # 用 pytest.exit 代替 sys.exit，避免 PluggyTeardownRaisedWarning
        pytest.exit(
            f"请使用项目虚拟环境运行测试！\n"
            f"当前 Python: {python_path}\n"
            f"建议: f:\\XU\\API-Automated-Testing\\.venv\\Scripts\\python.exe -m pytest",
            returncode=1,
        )

check_venv()

# ---------- 确保报告目录存在 ----------

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


# ---------- loguru 日志捕获：失败时附加到报告 ----------

# 每个测试用例的日志缓冲区 {nodeid: {buffer, handler_id}}
_log_buffers = {}


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_setup(item):
    """测试开始前：为每个用例创建日志缓冲区，捕获 loguru 输出"""
    buffer = io.StringIO()
    handler_id = logger.add(
        buffer,
        format="{time:HH:mm:ss} | {level: <7} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        filter=lambda record: record["level"].name in ("DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR"),
    )
    _log_buffers[item.nodeid] = {"buffer": buffer, "handler_id": handler_id}
    yield


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_teardown(item, nextitem):
    """测试结束后：移除日志 handler"""
    info = _log_buffers.pop(item.nodeid, None)
    if info:
        try:
            logger.remove(info["handler_id"])
        except ValueError:
            pass
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """生成报告：失败时把 loguru 日志写入 report.sections，并记录环境标签

    此 hook 以 hookwrapper 方式包装，确保在 report 生成后还能追加内容。
    """
    outcome = yield
    report = outcome.get_result()

    # 记录当前环境到 user_properties，供 HTML 表格的「环境」列读取
    if report.when == "call":
        try:
            from core.env_manager import get_env_manager
            env_name = get_env_manager().current_env
            report.user_properties.append(("env", env_name))
        except Exception:
            report.user_properties.append(("env", "-"))

    # 失败时附加 loguru 日志
    if report.when == "call" and report.failed:
        info = _log_buffers.get(item.nodeid)
        if info:
            log_content = info["buffer"].getvalue()
            if log_content:
                # pytest-html 会渲染 sections 中的内容
                report.sections.append(("loguru 日志", log_content))


# ---------- HTML 报告元数据 ----------

def pytest_configure(config):
    """配置阶段：注入环境元数据到报告"""
    config._metadata = getattr(config, "_metadata", {})
    env_name = "未加载"
    base_url = "N/A"
    db_host = "N/A"
    try:
        from core.env_manager import get_env_manager
        mgr = get_env_manager()
        env_name = mgr.current_env
        base_url = mgr.base_url
        db_host = mgr.get("db.host", "N/A")
        config._metadata["测试环境"] = env_name
        config._metadata["Base URL"] = base_url
        config._metadata["数据库"] = db_host
    except Exception:
        config._metadata["测试环境"] = env_name

    config._metadata["Python"] = sys.version.split()[0]
    config._metadata["Platform"] = sys.platform
    config._metadata["执行时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 保存到 config 供 pytest_sessionstart 写入（allure 的 clean_alluredir 在 configure 后执行）
    config._allure_env_info = {
        "Test.Env": env_name,
        "Base.URL": base_url,
        "DB.Host": db_host,
        "Python": sys.version.split()[0],
    }


def pytest_sessionstart(session):
    """会话开始：在 allure 清理目录后写入 environment.properties"""
    config = session.config
    env_info = getattr(config, "_allure_env_info", None)
    if not env_info:
        return
    try:
        allure_dir = config.getoption("allure_report_dir", default=None)
        if allure_dir:
            os.makedirs(allure_dir, exist_ok=True)
            env_path = os.path.join(allure_dir, "environment.properties")
            with open(env_path, "w", encoding="utf-8") as f:
                for key, value in env_info.items():
                    f.write(f"{key}={value}\n")
    except Exception:
        pass


def pytest_html_report_title(report):
    """自定义报告标题"""
    report.title = "API 自动化测试报告"


def pytest_html_results_summary(prefix, summary, postfix):
    """自定义 HTML 报告的摘要区域"""
    prefix.extend([
        '<p style="font-size:14px;color:#666;">API 自动化测试报告 · 由 pytest-html 生成</p>',
    ])


def pytest_html_results_table_header(cells):
    """在结果表头添加「环境」列"""
    cells.insert(2, '<th>环境</th>')


def pytest_html_results_table_row(report, cells):
    """在结果行填入环境列（从 user_properties 读取）"""
    env = "-"
    for name, value in getattr(report, "user_properties", []):
        if name == "env":
            env = value
            break
    cells.insert(2, f'<td>{env}</td>')
