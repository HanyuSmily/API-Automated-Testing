"""一键运行测试并生成可视化报告

用法:
    # 默认运行全部测试（生成 pytest-html 报告 + allure 原始数据）
    python run_tests.py

    # 指定环境
    python run_tests.py --env qa

    # 仅运行某个标记
    python run_tests.py -m api

    # 生成 Allure 最终报告（需本机已安装 allure CLI）
    python run_tests.py --allure
"""
import argparse
import os
import subprocess
import sys

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
HTML_REPORT = os.path.join(REPORTS_DIR, "report.html")
ALLURE_DATA_DIR = os.path.join(REPORTS_DIR, "allure_data")
ALLURE_REPORT_DIR = os.path.join(REPORTS_DIR, "allure_report")


def main():
    parser = argparse.ArgumentParser(description="API 自动化测试运行器")
    parser.add_argument("--env", default=None, help="测试环境 (dev/qa/prod)，不指定则用 env.yml 默认值")
    parser.add_argument("-m", default=None, help="pytest 标记表达式，如 'api'、'env or assert'")
    parser.add_argument("--allure", action="store_true", help="运行后生成 Allure HTML 报告（需 allure CLI）")
    parser.add_argument("--open", action="store_true", help="运行后自动打开 HTML 报告")
    args, extra = parser.parse_known_args()

    # 构造 pytest 命令
    cmd = [VENV_PYTHON, "-m", "pytest"]

    if args.m:
        cmd += ["-m", args.m]

    cmd += extra  # 透传其他 pytest 参数

    # 设置环境变量
    env = os.environ.copy()
    if args.env:
        env["TEST_ENV"] = args.env
        print(f">>> 使用测试环境: {args.env}")
    else:
        print(">>> 使用 env.yml 默认环境")

    print(f">>> 执行命令: {' '.join(cmd)}\n")

    # 运行 pytest
    result = subprocess.run(cmd, env=env, cwd=PROJECT_ROOT)

    # 生成 Allure 报告
    if args.allure:
        print("\n>>> 生成 Allure HTML 报告...")
        allure_cmd = ["allure", "generate", ALLURE_DATA_DIR, "-o", ALLURE_REPORT_DIR, "--clean"]
        allure_result = subprocess.run(allure_cmd)
        if allure_result.returncode == 0:
            print(f">>> Allure 报告已生成: {ALLURE_REPORT_DIR}")
        else:
            print(">>> Allure 报告生成失败，请确认已安装 allure CLI: https://allurereport.org/docs/install/")

    # 自动打开报告
    if args.open and os.path.isfile(HTML_REPORT):
        print(f"\>>> 打开 HTML 报告: {HTML_REPORT}")
        if sys.platform == "win32":
            os.startfile(HTML_REPORT)
        elif sys.platform == "darwin":
            subprocess.run(["open", HTML_REPORT])
        else:
            subprocess.run(["xdg-open", HTML_REPORT])

    # 汇总
    print("\n" + "=" * 60)
    print(f"HTML 报告: {HTML_REPORT}")
    print(f"Allure 数据: {ALLURE_DATA_DIR}")
    if os.path.isdir(ALLURE_REPORT_DIR):
        print(f"Allure 报告: {ALLURE_REPORT_DIR}")
    print("=" * 60)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
