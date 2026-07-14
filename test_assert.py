import pytest
from unittest.mock import patch, MagicMock

from core.runner import SessionRunner
from core.client import HttpSession
from core.step import Step
from utils.assert_utils import AssertUtils


# ---------- AssertUtils 单元测试 ----------

class TestAssertUtilsBasic:
    """基础断言类型测试"""

    def test_eq_pass(self):
        AssertUtils.validate(200, 200, "eq")

    def test_eq_fail(self):
        with pytest.raises(AssertionError):
            AssertUtils.validate(200, 404, "eq")

    def test_ne_pass(self):
        AssertUtils.validate(200, 404, "ne")

    def test_contains_pass(self):
        AssertUtils.validate("hello world", "world", "contains")

    def test_contained_by_pass(self):
        AssertUtils.validate("apple", ["apple", "banana"], "contained_by")
    #比较
    def test_gt_ge_lt_le(self):
        AssertUtils.validate(10, 5, "gt")
        AssertUtils.validate(10, 10, "ge")
        AssertUtils.validate(5, 10, "lt")
        AssertUtils.validate(10, 10, "le")
    #长度
    def test_len_assertions(self):
        AssertUtils.validate([1, 2, 3], 3, "len_eq")
        AssertUtils.validate([1, 2, 3], 2, "len_gt")
        AssertUtils.validate([1, 2, 3], 4, "len_lt")


class TestAssertUtilsType:
    """类型断言测试"""

    def test_type_int(self):
        AssertUtils.validate(123, "int", "type")

    def test_type_str(self):
        AssertUtils.validate("abc", "str", "type")

    def test_type_list(self):
        AssertUtils.validate([1, 2], "list", "type")

    def test_type_dict(self):
        AssertUtils.validate({"a": 1}, "dict", "type")

    def test_type_bool(self):
        AssertUtils.validate(True, "bool", "type")

    def test_type_null(self):
        AssertUtils.validate(None, "null", "type")

    def test_type_int_rejects_bool(self):
        # bool 不应被当作 int 通过
        with pytest.raises(AssertionError):
            AssertUtils.validate(True, "int", "type")

    def test_type_fail(self):
        with pytest.raises(AssertionError):
            AssertUtils.validate("abc", "int", "type")


class TestAssertUtilsRegex:
    """正则断言测试"""

    def test_regex_pass(self):
        AssertUtils.validate("token_abc123", r"token_[a-z0-9]+", "regex")

    def test_regex_email(self):
        AssertUtils.validate("user@example.com", r"^[\w.]+@[\w]+\.[\w]+$", "regex")

    def test_regex_fail(self):
        with pytest.raises(AssertionError):
            AssertUtils.validate("abc", r"^\d+$", "regex")


# ---------- JSON Schema 断言测试 ----------

class TestJsonSchema:
    """JSON Schema 校验测试"""

    def test_schema_pass(self):
        """符合 Schema 的响应校验通过"""
        schema = {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0},
            },
        }
        actual = {"id": 1, "name": "alice", "age": 25}
        AssertUtils.validate(actual, schema, "json_schema")

    def test_schema_missing_required(self):
        """缺少必填字段应校验失败"""
        schema = {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
            },
        }
        actual = {"id": 1}#缺少必填的name、age
        with pytest.raises(AssertionError) as exc_info:
            AssertUtils.validate(actual, schema, "json_schema")
        assert "name" in str(exc_info.value)

    def test_schema_wrong_type(self):
        """字段类型错误应校验失败"""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
            },
        }
        actual = {"id": "not_an_int"}
        with pytest.raises(AssertionError) as exc_info:
            AssertUtils.validate(actual, schema, "json_schema")
        assert "integer" in str(exc_info.value)

    def test_schema_array(self):
        """数组类型 Schema 校验"""
        schema = {
            "type": "array",
            "items": {"type": "integer"},
            "minItems": 1,
        }
        AssertUtils.validate([1, 2, 3], schema, "json_schema")

    def test_schema_nested(self):
        """嵌套对象 Schema 校验"""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "integer"},
                        "profile": {
                            "type": "object",
                            "properties": {
                                "email": {"type": "string", "format": "email"},
                            },
                        },
                    },
                },
            },
        }
        actual = {"user": {"id": 1, "profile": {"email": "a@b.com"}}}
        AssertUtils.validate(actual, schema, "json_schema")


# ---------- Step 集成测试 ----------

class TestStepAssertions:
    """验证 Step 中各类断言类型在实际流程中生效"""

    def _build_runner(self):
        runner = SessionRunner()
        from httprunner.models import TConfig
        runner.config = TConfig(name="断言用例", base_url="https://api.example.com", variables={})
        runner.session_variables = {}
        return runner

    def _mock_resp(self, status_code=200, json_data=None, headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.headers = headers or {"Content-Type": "application/json"}
        return resp

    def test_step_json_schema_assertion(self):
        """验证 Step 中对整个响应体做 json_schema 校验"""
        runner = self._build_runner()
        schema = {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
            },
        }
        step = Step(
            name="schema 校验",
            request={"url": "/user", "method": "GET"},
            validate=[
                {"check": "status_code", "assert_type": "eq", "expect": 200},
                {"check": "body", "assert_type": "json_schema", "expect": schema},
            ],
        )
        fake_resp = self._mock_resp(json_data={"id": 1, "name": "alice"})
        with patch.object(HttpSession, "request", return_value=fake_resp):
            result = step.run(runner)
        assert result["success"] is True

    def test_step_type_and_regex_assertion(self):
        """验证 Step 中 type 与 regex 断言"""
        runner = self._build_runner()
        step = Step(
            name="类型与正则校验",
            request={"url": "/user", "method": "GET"},
            validate=[
                {"check": "id", "assert_type": "type", "expect": "int"},
                {"check": "name", "assert_type": "regex", "expect": r"^alice$"},
                {"check": "tags", "assert_type": "len_eq", "expect": 3},
            ],
        )
        fake_resp = self._mock_resp(json_data={"id": 1, "name": "alice", "tags": ["a", "b", "c"]})
        with patch.object(HttpSession, "request", return_value=fake_resp):
            result = step.run(runner)
        assert result["success"] is True

    def test_step_schema_assertion_fails(self):
        """验证 Schema 校验失败时 Step 抛出异常"""
        runner = self._build_runner()
        schema = {
            "type": "object",
            "required": ["id", "email"],
            "properties": {
                "id": {"type": "integer"},
                "email": {"type": "string"},
            },
        }
        step = Step(
            name="schema 校验失败",
            request={"url": "/user", "method": "GET"},
            validate=[
                {"check": "body", "assert_type": "json_schema", "expect": schema},
            ],
        )
        # 缺少 email 字段
        fake_resp = self._mock_resp(json_data={"id": 1})
        with patch.object(HttpSession, "request", return_value=fake_resp):
            with pytest.raises(AssertionError) as exc_info:
                step.run(runner)
        assert "email" in str(exc_info.value)
