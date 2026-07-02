import pytest
from core.runner import SessionRunner
from core.client import HttpSession
from httprunner.models import TConfig, TestCase


def get_testcase_data():
    return {
        "config": TConfig(name="测试GET 请求", base_url="https://httpbin.org", variables={"user_id": 123}),
        "teststeps": [
            {
                "name": "测试 GET 请求",
                "request": {"url": "/get?id=$user_id", "method": "GET"},
                "validate": [{"check": "status_code", "assert_type": "eq", "expect": 200}]
            }
        ]
    }


def test_api_flow():
    runner = SessionRunner()
    testcase = get_testcase_data()
    runner.teststeps = testcase["teststeps"]
    runner.config = testcase["config"]
    runner.test_start()

    assert runner.get_summary().success is True
    print("测试运行完成，全部通过！")