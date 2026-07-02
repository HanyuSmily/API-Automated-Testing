import re
from httprunner.parser import parse_data # 直接复用核心解析逻辑

class Parser:
    def __init__(self, functions_mapping=None):
        self.functions_mapping = functions_mapping or {}

    def parse_variables(self, raw_data, variables):
        """
        将数据中的变量占位符替换为真实值
        例如: {"url": "/api/$id"} -> {"url": "/api/1001"}
        """
        return parse_data(raw_data, variables, self.functions_mapping)

    def extract_field(self, response_json, jmespath_expression):
        """
        利用 jmespath 从响应体中提取字段
        """
        import jmespath

        return jmespath.search(jmespath_expression, response_json)