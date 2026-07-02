import re
from typing import Any

from loguru import logger


class AssertUtils:
    """通用断言工具集：支持值比较、包含、类型、长度、正则、JSON Schema 校验"""

    @staticmethod
    def validate(actual_value: Any, expected_value: Any, assert_type: str = "eq"):
        """通用断言分发器

        Args:
            actual_value: 接口返回的实际值
            expected_value: 预期的值（json_schema 类型时为 Schema 字典）
            assert_type: 断言类型
                - eq: 相等
                - ne: 不等
                - contains: 实际值包含预期值
                - contained_by: 实际值被预期值包含
                - gt / ge / lt / le: 大小比较
                - len_eq / len_gt / len_lt: 长度比较
                - type: 类型校验（int/str/list/dict/bool/float/null）
                - regex: 正则匹配
                - json_schema: JSON Schema 校验（expected_value 为 Schema）
        """
        logger.info(f"执行校验: 实际值 {actual_value} vs 预期值 {expected_value} (类型: {assert_type})")

        handler = _ASSERT_HANDLERS.get(assert_type)
        if handler is None:
            raise ValueError(f"不支持的断言类型: {assert_type}（支持: {list(_ASSERT_HANDLERS.keys())}）")

        handler(actual_value, expected_value)
        logger.success("校验通过")


# ---------- 类型校验辅助 ----------

# assert_type=type 时，字符串 -> Python 类型的映射
_TYPE_MAP = {
    "int": int,
    "str": str,
    "list": list,
    "dict": dict,
    "bool": bool,
    "float": float,
    "NoneType": type(None),
    "null": type(None),
}


def _assert_eq(actual, expected):
    assert actual == expected, f"校验失败: {actual} != {expected}"


def _assert_ne(actual, expected):
    assert actual != expected, f"校验失败: {actual} 不应等于 {expected}"


def _assert_contains(actual, expected):
    assert expected in actual, f"校验失败: {expected} 不在 {actual} 中"


def _assert_contained_by(actual, expected):
    assert actual in expected, f"校验失败: {actual} 不在 {expected} 中"


def _assert_gt(actual, expected):
    assert actual > expected, f"校验失败: {actual} 不大于 {expected}"


def _assert_ge(actual, expected):
    assert actual >= expected, f"校验失败: {actual} 小于 {expected}"


def _assert_lt(actual, expected):
    assert actual < expected, f"校验失败: {actual} 不小于 {expected}"


def _assert_le(actual, expected):
    assert actual <= expected, f"校验失败: {actual} 大于 {expected}"


def _assert_len_eq(actual, expected):
    actual_len = len(actual)
    assert actual_len == expected, f"校验失败: 长度 {actual_len} != {expected}"


def _assert_len_gt(actual, expected):
    actual_len = len(actual)
    assert actual_len > expected, f"校验失败: 长度 {actual_len} 不大于 {expected}"


def _assert_len_lt(actual, expected):
    actual_len = len(actual)
    assert actual_len < expected, f"校验失败: 长度 {actual_len} 不小于 {expected}"


def _assert_type(actual, expected):
    """类型校验，expected 为类型名字符串，如 'str' / 'int'"""
    expected_type = _TYPE_MAP.get(expected)
    if expected_type is None:
        raise ValueError(f"不支持的类型名: {expected}（支持: {list(_TYPE_MAP.keys())}）")
    # 注意：bool 是 int 的子类，需特殊处理避免 True 被当作 int 通过
    if expected_type == int and isinstance(actual, bool):
        assert False, f"校验失败: 期望 int，实际为 bool"
    if expected_type == bool:
        assert isinstance(actual, bool), f"校验失败: 期望 bool，实际为 {type(actual).__name__}"
    else:
        assert isinstance(actual, expected_type), f"校验失败: 期望 {expected}，实际为 {type(actual).__name__}"


def _assert_regex(actual, expected):
    """正则匹配，expected 为正则表达式字符串"""
    assert re.search(expected, str(actual)) is not None, f"校验失败: {actual} 不匹配正则 {expected}"


def _assert_json_schema(actual, expected):
    """JSON Schema 校验，expected 为 JSON Schema 字典

    示例:
        validate:
          - check: body
            assert_type: json_schema
            expect:
              type: object
              required: [id, name]
              properties:
                id: {type: integer}
                name: {type: string}
    """
    # 延迟导入，避免未安装 jsonschema 时影响其他断言
    import jsonschema

    try:
        jsonschema.validate(instance=actual, schema=expected)
    except jsonschema.ValidationError as e:
        # 抛出断言错误，附带具体校验失败路径与原因
        raise AssertionError(f"JSON Schema 校验失败: {e.message} (路径: {list(e.absolute_path)})") from e


# 断言类型 -> 处理函数 映射表
_ASSERT_HANDLERS = {
    "eq": _assert_eq,
    "ne": _assert_ne,
    "contains": _assert_contains,
    "contained_by": _assert_contained_by,
    "gt": _assert_gt,
    "ge": _assert_ge,
    "lt": _assert_lt,
    "le": _assert_le,
    "len_eq": _assert_len_eq,
    "len_gt": _assert_len_gt,
    "len_lt": _assert_len_lt,
    "type": _assert_type,
    "regex": _assert_regex,
    "json_schema": _assert_json_schema,
}
