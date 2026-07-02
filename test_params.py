#这个文件做参数化测试
import pytest
from unittest.mock import patch, MagicMock

from core.runner import SessionRunner
from core.client import HttpSession
from core.step import Step
from data.parms import load_params


# 预加载数据（相对 data/ 目录），并对 CSV 的字符串字段做类型转换
CSV_DATA = load_params("test_users.csv", converters={"user_id": int, "expect_status": int})
JSON_DATA = load_params("test_users.json")
EXCEL_DATA = load_params("test_users.xlsx")

# 合并三种来源的数据，统一驱动同一个用例
ALL_DATA = CSV_DATA + JSON_DATA + EXCEL_DATA


def test_data_loader_supports_all_formats():
    """验证 DataLoader 能正确解析 CSV / JSON / Excel 三种格式"""
    assert len(CSV_DATA) == 3
    assert len(JSON_DATA) == 3
    assert len(EXCEL_DATA) == 3

    # CSV 经类型转换后 user_id 应为 int
    assert CSV_DATA[0]["user_id"] == 101
    assert isinstance(CSV_DATA[0]["user_id"], int)

    # JSON 字段保持原类型
    assert JSON_DATA[0]["user_id"] == 201

    # Excel 字段保持原类型
    assert EXCEL_DATA[0]["user_id"] == 301


@pytest.mark.parametrize("params", ALL_DATA)
def test_parametrized_runner_local(params):
    """数据驱动测试（本地 mock，不依赖外部网络）：
    用外部数据文件循环执行同一个用例，验证参数化注入机制。
    """
    user_id = params["user_id"]
    expect_status = params["expect_status"]

    runner = SessionRunner()
    from httprunner.models import TConfig

    runner.config = TConfig(
        name=f"参数化用例-user_id={user_id}",
        base_url="https://httpbin.org",
        variables={"user_id": user_id},
    )
    runner.session_variables = {"user_id": user_id}

    step = Step(
        name=f"GET 请求 user_id={user_id}",
        request={"url": "/get?id=$user_id", "method": "GET"},
        validate=[{"check": "status_code", "assert_type": "eq", "expect": expect_status}],
    )

    # mock 父类 request，避免真实网络调用
    fake_resp = MagicMock()
    fake_resp.status_code = expect_status
    fake_resp.json.return_value = {"args": {"id": str(user_id)}}

    with patch.object(HttpSession, "request", return_value=fake_resp):
        result = step.run(runner)

    assert result["success"] is True


@pytest.mark.parametrize("params", load_params("test_users.csv", converters={"user_id": int, "expect_status": int}))
def test_parametrize_with_csv_data(params):
    """验证 pytest.mark.parametrize 能直接消费 load_params 返回的 dict 列表"""
    assert "user_id" in params
    assert "expect_status" in params
    assert isinstance(params["user_id"], int)
