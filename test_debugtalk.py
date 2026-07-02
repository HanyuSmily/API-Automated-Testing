import time

import pytest
from unittest.mock import patch, MagicMock

from core.loader import load_debugtalk, get_project_root
from core.runner import SessionRunner
from core.client import HttpSession
from core.step import Step
from core.parser import Parser

#验证测试，7 个测试覆盖：
# 函数加载、自动加载、 ${get_token()} 调用、带参调用 ${add($a,$b)} 、签名函数、Step 请求中调用、变量与函数混合使用。

def test_debugtalk_functions_loaded():
    """验证 debugtalk.py 中的公共函数被正确加载"""
    project_root = get_project_root()
    meta = load_debugtalk(project_root)

    # 应加载到这些函数
    expected = {"get_token", "gen_timestamp", "gen_random_string", "sign", "add", "gen_user_id"}
    assert expected.issubset(set(meta.functions.keys())), f"缺少函数: {expected - set(meta.functions.keys())}"

    # 私有函数不应被加载（以下划线开头）
    for name in meta.functions:
        assert not name.startswith("_")


def test_runner_auto_loads_debugtalk():
    """验证 SessionRunner 无 project_meta 时自动加载 debugtalk.py"""
    runner = SessionRunner()
    # parser 中应包含 debugtalk 函数
    assert "get_token" in runner.parser.functions_mapping
    assert "sign" in runner.parser.functions_mapping


def test_function_call_in_variables():
    """验证 ${get_token()} 在变量中被正确解析"""
    parser = Parser(load_debugtalk(get_project_root()).functions)

    # 模拟用例中通过 ${func()} 调用自定义函数
    raw = {"token": "${get_token()}", "ts": "${gen_timestamp()}"}
    parsed = parser.parse_variables(raw, {})

    # token 应以 token_ 开头
    assert parsed["token"].startswith("token_")
    # ts 应为当前时间戳（允许 5 秒误差）
    assert abs(parsed["ts"] - int(time.time())) <= 5


def test_function_call_with_args():
    """验证带参数的函数调用 ${add($a, $b)}"""
    parser = Parser(load_debugtalk(get_project_root()).functions)

    raw = {"sum": "${add($a, $b)}"}
    parsed = parser.parse_variables(raw, {"a": 3, "b": 5})
    assert parsed["sum"] == 8


def test_sign_function():
    """验证签名计算函数"""
    parser = Parser(load_debugtalk(get_project_root()).functions)

    raw = {"signature": "${sign($params)}"}
    params = {"id": 123, "name": "abc"}
    parsed = parser.parse_variables(raw, {"params": params})

    # 签名应为 32 位 MD5
    assert len(parsed["signature"]) == 32


def test_function_call_in_step_request():
    """验证 ${func()} 在 Step 请求中被正确解析（mock 网络层）"""
    runner = SessionRunner()
    from httprunner.models import TConfig

    runner.config = TConfig(
        name="debugtalk 用例",
        base_url="https://httpbin.org",
        variables={},
    )
    runner.session_variables = {}

    # 请求 URL 中通过 ${gen_user_id()} 动态生成用户 ID
    step = Step(
        name="带自定义函数的请求",
        request={"url": "/get?id=${gen_user_id()}", "method": "GET"},
        validate=[{"check": "status_code", "assert_type": "eq", "expect": 200}],
    )

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"args": {"id": "9999"}}

    captured = {}

    def fake_request(self, method, url, **kwargs):
        captured["url"] = url
        return fake_resp

    with patch.object(HttpSession, "request", new=fake_request):
        result = step.run(runner)

    assert result["success"] is True
    # URL 中应已被替换为具体数字（不再是 ${gen_user_id()}）
    assert "${gen_user_id()}" not in captured["url"]
    assert "/get?id=" in captured["url"]


def test_function_call_mixed_with_variables():
    """验证变量与函数混合使用：$token 和 ${get_token()} 同时出现"""
    parser = Parser(load_debugtalk(get_project_root()).functions)

    raw = {"header": "Bearer ${get_token()}", "ref": "$token"}
    parsed = parser.parse_variables(raw, {"token": "preset_token"})

    assert parsed["header"].startswith("Bearer token_")
    assert parsed["ref"] == "preset_token"
