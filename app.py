import streamlit as st
import os
import sys
import subprocess
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.env_manager import get_env_manager, reset_env_manager

st.set_page_config(
    page_title="API 自动化测试平台",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

ENV_OPTIONS = {
    "mock": "🟢 Mock 环境（本地）",
    "dev": "🔵 开发环境（远端）",
    "qa": "🟡 测试环境（远端）",
    "prod": "🔴 生产环境（只读）"
}


def run_tests(env_name: str, test_path: str = "testcases/"):
    """运行 pytest 测试并返回结果"""
    env = os.environ.copy()
    env["TEST_ENV"] = env_name
    env["PYTHONUNBUFFERED"] = "1"

    allure_dir = "reports/allure_results"

    cmd = [
        sys.executable, "-m", "pytest", test_path,
        "-v", "-s",
        "--alluredir", allure_dir,
        "--clean-alluredir"
    ]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def generate_allure_report():
    """生成 Allure HTML 报告"""
    allure_results = "reports/allure_results"
    allure_report = "reports/allure_report"

    if not os.path.isdir(allure_results) or not os.listdir(allure_results):
        return False, "暂无测试结果数据，请先运行测试"

    cmd = ["allure", "generate", allure_results, "-o", allure_report, "--clean"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        if result.returncode == 0:
            return True, allure_report
        else:
            return False, result.stderr
    except FileNotFoundError:
        return False, "未找到 allure 命令，请先安装 Allure CLI"
    except Exception as e:
        return False, str(e)


def get_test_summary():
    """从 allure 结果中读取测试概要"""
    allure_results = "reports/allure_results"
    summary_file = os.path.join(allure_results, "..", "allure_report", "widgets", "summary.json")

    if not os.path.isfile(summary_file):
        return None

    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


st.title("🚀 API 自动化测试平台")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ 测试配置")

    env_key = st.selectbox(
        "选择测试环境",
        options=list(ENV_OPTIONS.keys()),
        format_func=lambda x: ENV_OPTIONS[x],
        index=0
    )

    test_scope = st.radio(
        "测试范围",
        options=["全部用例", "订单模块", "商品模块", "指定文件"],
        index=0
    )

    test_path = "testcases/"
    if test_scope == "订单模块":
        test_path = "testcases/test_mall_order_e2e.py"
    elif test_scope == "商品模块":
        test_path = "testcases/test_mall_order_e2e.py::test_product_list_pagination"
    elif test_scope == "指定文件":
        test_path = st.text_input("用例路径", value="testcases/test_mall_order_e2e.py")

    st.markdown("---")
    st.subheader("📊 环境信息")

    try:
        reset_env_manager()
        env_mgr = get_env_manager()
        st.info(f"**当前环境**: {env_key.upper()}\n\n**Base URL**: {env_mgr.base_url}")

        if env_mgr.is_mock_env():
            st.success("✅ Mock 环境 - 安全测试，不影响真实数据")
        elif env_key == "prod":
            st.error("⚠️ 生产环境 - 仅支持只读测试")
    except Exception as e:
        st.error(f"加载配置失败: {e}")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🎯 一键运行")

    run_btn = st.button(
        "▶️ 运行测试",
        type="primary",
        use_container_width=True,
        help=f"在 {ENV_OPTIONS[env_key]} 下运行 {test_scope}"
    )

    st.markdown("---")
    st.subheader("📈 快捷操作")

    if st.button("🔄 重置 Mock 数据", use_container_width=True):
        try:
            import requests
            r = requests.post("http://127.0.0.1:8080/reset", timeout=5)
            if r.status_code == 200:
                st.success("Mock 数据已重置")
            else:
                st.warning("重置失败，请检查 Mock 服务")
        except Exception as e:
            st.error(f"连接 Mock 服务失败: {e}")

    if st.button("📊 生成 Allure 报告", use_container_width=True):
        with st.spinner("正在生成报告..."):
            ok, msg = generate_allure_report()
            if ok:
                st.success(f"报告已生成: {msg}")
            else:
                st.error(msg)

with col2:
    st.subheader("📋 测试执行")

    if run_btn:
        with st.spinner(f"正在 {ENV_OPTIONS[env_key]} 下运行测试..."):
            returncode, stdout, stderr = run_tests(env_key, test_path)

        if returncode == 0:
            st.success("✅ 全部测试通过！")
        elif returncode == 1:
            st.warning("⚠️ 存在测试失败")
        else:
            st.error(f"❌ 测试执行失败 (退出码: {returncode})")

        with st.expander("📝 查看完整输出", expanded=True):
            st.code(stdout, language="text")
            if stderr:
                st.markdown("**错误输出:**")
                st.code(stderr, language="text")

        with st.spinner("正在生成 Allure 报告..."):
            ok, msg = generate_allure_report()
            if ok:
                st.success(f"📊 Allure 报告已生成")
            else:
                st.info(f"报告生成提示: {msg}")

st.markdown("---")
st.subheader("📊 Allure 测试报告")

report_dir = "reports/allure_report"
index_html = os.path.join(report_dir, "index.html")

if os.path.isfile(index_html):
    st.info("📂 报告已生成，可通过以下方式查看：")

    tab1, tab2 = st.tabs(["📊 报告概览", "🔧 报告工具"])

    with tab1:
        summary = get_test_summary()
        if summary:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                total = summary.get("statistic", {}).get("total", 0)
                st.metric("用例总数", total)
            with c2:
                passed = summary.get("statistic", {}).get("passed", 0)
                st.metric("通过", passed, delta_color="normal")
            with c3:
                failed = summary.get("statistic", {}).get("failed", 0)
                st.metric("失败", failed, delta_color="inverse")
            with c4:
                broken = summary.get("statistic", {}).get("broken", 0)
                st.metric("阻塞", broken, delta_color="inverse")
        else:
            st.info("暂无报告统计数据，请先运行测试")

    with tab2:
        st.markdown("### 启动 Allure 报告服务")
        st.code("allure serve reports/allure_results", language="bash")
        st.markdown("### 或直接打开 HTML")
        st.code(f"start {index_html}", language="bash")

    st.markdown("---")
    st.caption("💡 提示：由于浏览器安全策略，内嵌 iframe 可能无法完整加载 Allure 报告。推荐使用 `allure serve` 命令启动独立服务查看。")
else:
    st.info("📭 暂无报告，请先运行测试")
    st.markdown("运行测试后，Allure 报告会自动生成到 `reports/allure_report/` 目录。")

st.markdown("---")
st.caption("API 自动化测试平台 | 基于 pytest + requests + Allure + Streamlit")
