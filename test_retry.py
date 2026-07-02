import pytest
from unittest.mock import patch, MagicMock

import requests

from core.runner import SessionRunner
from core.client import HttpSession
from core.step import Step, RETRYABLE_EXCEPTIONS


def _build_runner():
    """构造一个带 config 的 runner"""
    runner = SessionRunner()
    from httprunner.models import TConfig
    runner.config = TConfig(name="重试用例", base_url="https://api.example.com", variables={})
    runner.session_variables = {}
    return runner


def _mock_resp(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = {}
    return resp


# ---------- 不重试场景 ----------

class TestNoRetry:
    """retry_times=0 时不应重试"""

    def test_success_no_retry(self):
        """成功时不重试，只请求一次"""
        runner = _build_runner()
        step = Step(name="成功", request={"url": "/ok", "method": "GET"}, retry_times=0)

        call_count = {"n": 0}

        def fake_request(self, method, url, **kwargs):
            call_count["n"] += 1
            return _mock_resp(200, {"id": 1})

        with patch.object(HttpSession, "request", new=fake_request):
            result = step.run(runner)

        assert result["success"] is True
        assert call_count["n"] == 1  # 只调用一次

    def test_failure_no_retry_raises(self):
        """retry_times=0 时失败直接抛出，不重试"""
        runner = _build_runner()
        step = Step(
            name="失败不重试",
            request={"url": "/fail", "method": "GET"},
            validate=[{"check": "status_code", "assert_type": "eq", "expect": 200}],
            retry_times=0,
        )

        call_count = {"n": 0}

        def fake_request(self, method, url, **kwargs):
            call_count["n"] += 1
            return _mock_resp(500)

        with patch.object(HttpSession, "request", new=fake_request):
            with pytest.raises(AssertionError):
                step.run(runner)

        assert call_count["n"] == 1  # 只调用一次，未重试


# ---------- 重试成功场景 ----------

class TestRetrySuccess:
    """重试后成功的场景"""

    def test_retry_then_success(self):
        """前两次失败，第三次成功"""
        runner = _build_runner()
        step = Step(
            name="重试后成功",
            request={"url": "/flaky", "method": "GET"},
            validate=[{"check": "status_code", "assert_type": "eq", "expect": 200}],
            retry_times=3,
            retry_interval=0,  # 测试中不等待
        )

        responses = [_mock_resp(500), _mock_resp(500), _mock_resp(200)]

        def fake_request(self, method, url, **kwargs):
            return responses.pop(0)

        with patch.object(HttpSession, "request", new=fake_request):
            result = step.run(runner)

        assert result["success"] is True
        assert len(responses) == 0  # 三个响应都被消费

    def test_retry_on_connection_error(self):
        """网络连接错误触发重试，最终成功"""
        runner = _build_runner()
        step = Step(
            name="网络错误重试",
            request={"url": "/net", "method": "GET"},
            retry_times=2,
            retry_interval=0,
        )

        call_count = {"n": 0}

        def fake_request(self, method, url, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise requests.exceptions.ConnectionError("连接失败")
            return _mock_resp(200)

        with patch.object(HttpSession, "request", new=fake_request):
            result = step.run(runner)

        assert result["success"] is True
        assert call_count["n"] == 2  # 第一次失败，第二次成功

    def test_retry_on_timeout(self):
        """超时错误触发重试"""
        runner = _build_runner()
        step = Step(
            name="超时重试",
            request={"url": "/slow", "method": "GET"},
            retry_times=2,
            retry_interval=0,
        )

        call_count = {"n": 0}

        def fake_request(self, method, url, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise requests.exceptions.Timeout("请求超时")
            return _mock_resp(200)

        with patch.object(HttpSession, "request", new=fake_request):
            result = step.run(runner)

        assert result["success"] is True
        assert call_count["n"] == 2


# ---------- 重试耗尽场景 ----------

class TestRetryExhausted:
    """重试次数用尽后仍失败"""

    def test_all_retries_fail_raises(self):
        """所有重试都失败后抛出最后的异常"""
        runner = _build_runner()
        step = Step(
            name="全部失败",
            request={"url": "/always_fail", "method": "GET"},
            validate=[{"check": "status_code", "assert_type": "eq", "expect": 200}],
            retry_times=2,
            retry_interval=0,
        )

        call_count = {"n": 0}

        def fake_request(self, method, url, **kwargs):
            call_count["n"] += 1
            return _mock_resp(500)

        with patch.object(HttpSession, "request", new=fake_request):
            with pytest.raises(AssertionError) as exc_info:
                step.run(runner)

        # 总调用次数 = 1（首次）+ 2（重试）= 3
        assert call_count["n"] == 3
        assert "500" in str(exc_info.value)

    def test_all_retries_connection_error(self):
        """网络错误重试耗尽后抛出 ConnectionError"""
        runner = _build_runner()
        step = Step(
            name="网络全挂",
            request={"url": "/down", "method": "GET"},
            retry_times=2,
            retry_interval=0,
        )

        call_count = {"n": 0}

        def fake_request(self, method, url, **kwargs):
            call_count["n"] += 1
            raise requests.exceptions.ConnectionError("服务不可用")

        with patch.object(HttpSession, "request", new=fake_request):
            with pytest.raises(requests.exceptions.ConnectionError):
                step.run(runner)

        assert call_count["n"] == 3  # 1 + 2 次重试


# ---------- 不可重试异常场景 ----------

class TestNonRetryableException:
    """配置类错误不应重试"""

    def test_value_error_not_retried(self):
        """ValueError（配置错误）不触发重试，直接抛出"""
        runner = _build_runner()
        step = Step(
            name="配置错误",
            request={"url": "/cfg", "method": "GET"},
            retry_times=3,
            retry_interval=0,
        )

        call_count = {"n": 0}

        def fake_request(self, method, url, **kwargs):
            call_count["n"] += 1
            raise ValueError("配置错误：缺少必要参数")

        with patch.object(HttpSession, "request", new=fake_request):
            with pytest.raises(ValueError):
                step.run(runner)

        # 只调用一次，未重试
        assert call_count["n"] == 1

    def test_key_error_not_retried(self):
        """KeyError 不触发重试"""
        runner = _build_runner()
        step = Step(
            name="KeyError",
            request={"url": "/key", "method": "GET"},
            retry_times=3,
            retry_interval=0,
        )

        call_count = {"n": 0}

        def fake_request(self, method, url, **kwargs):
            call_count["n"] += 1
            raise KeyError("missing_key")

        with patch.object(HttpSession, "request", new=fake_request):
            with pytest.raises(KeyError):
                step.run(runner)

        assert call_count["n"] == 1


# ---------- 重试间隔验证 ----------

class TestRetryInterval:
    """验证重试间隔"""

    def test_retry_interval_respected(self):
        """验证每次重试前确实等待了指定时间"""
        runner = _build_runner()
        step = Step(
            name="间隔验证",
            request={"url": "/interval", "method": "GET"},
            validate=[{"check": "status_code", "assert_type": "eq", "expect": 200}],
            retry_times=2,
            retry_interval=0.5,
        )

        def fake_request(self, method, url, **kwargs):
            return _mock_resp(500)

        sleep_calls = []
        with patch.object(HttpSession, "request", new=fake_request):
            with patch("core.step.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                with pytest.raises(AssertionError):
                    step.run(runner)

        # 重试 2 次，应 sleep 2 次，每次 0.5s
        assert sleep_calls == [0.5, 0.5]


# ---------- 重试异常类型验证 ----------

class TestRetryableExceptions:
    """验证 RETRYABLE_EXCEPTIONS 定义正确"""

    def test_retryable_types(self):
        """确认可重试异常类型包含网络错误和断言错误"""
        assert requests.exceptions.ConnectionError in RETRYABLE_EXCEPTIONS
        assert requests.exceptions.Timeout in RETRYABLE_EXCEPTIONS
        assert AssertionError in RETRYABLE_EXCEPTIONS

    def test_non_retryable_not_in_list(self):
        """确认配置类错误不在可重试列表"""
        assert ValueError not in RETRYABLE_EXCEPTIONS
        assert KeyError not in RETRYABLE_EXCEPTIONS
        assert TypeError not in RETRYABLE_EXCEPTIONS
