import time

import requests
from loguru import logger


# 可重试的异常类型：网络问题（连接/超时）和断言失败（偶发不稳定）
# 不可重试的异常（如 ValueError/KeyError 配置错误）会直接抛出，因为重试也不会改变结果
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.HTTPError,  # 5xx 服务端错误，可能瞬时恢复
    AssertionError,                 # 断言失败，接口偶发不稳定
)


class Step:
    def __init__(self, name, request, validate=None, retry_times=0, retry_interval=1):
        self.name = name
        self.request = request
        self.validate = validate or []
        # retry_times: 失败后的重试次数（0 表示不重试，只执行一次）
        self.retry_times = retry_times
        # retry_interval: 每次重试前的等待秒数，给服务端恢复时间
        self.retry_interval = retry_interval

    def run(self, runner):
        """执行步骤（含重试编排，控制尝试次数、等待间隔、异常分流）

        总尝试次数 = 1（首次）+ retry_times（重试）
        仅对网络异常和断言失败重试，配置类错误（ValueError/KeyError）直接抛出。
        """
        logger.info(f"执行步骤: {self.name}")

        last_exception = None
        total_attempts = 1 + self.retry_times

        for attempt in range(1, total_attempts + 1):
            if attempt > 1:
                logger.warning(
                    f"步骤 [{self.name}] 第 {attempt - 1}/{self.retry_times} 次重试"
                    f"（等待 {self.retry_interval}s）"
                )
                time.sleep(self.retry_interval)

            try:
                result = self._execute(runner)
                if attempt > 1:
                    logger.success(f"步骤 [{self.name}] 第 {attempt} 次尝试成功")
                return result
            except RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                remaining = total_attempts - attempt
                if remaining > 0:
                    logger.warning(f"步骤 [{self.name}] 第 {attempt} 次尝试失败: {type(e).__name__}: {e}（剩余重试 {remaining} 次）")
                else:
                    logger.error(f"步骤 [{self.name}] 重试 {self.retry_times} 次后仍失败: {type(e).__name__}: {e}")
            # 非 RETRYABLE_EXCEPTIONS 的异常不会被捕获，直接向上抛出

        # 所有重试用尽，抛出最后一次异常
        raise last_exception

    def _execute(self, runner):
        """单次执行：发送请求 + 断言校验（不含重试逻辑）"""
        # 解析请求中的变量/函数占位符
        parsed_request = runner.parser.parse_variables(self.request, runner.session_variables)

        url = parsed_request.get("url", "")
        base_url = getattr(runner.config, "base_url", "")
        #若URL是相对路径则拼接完整URL
        if url and not url.startswith(("http://", "https://")):
            url = base_url + url
        parsed_request["url"] = url

        # 发送请求
        resp = runner.session.request(**parsed_request)

        # 解析响应体一次，供 body / jmespath 字段断言复用
        try:
            resp_json = resp.json()
        except Exception:
            resp_json = None

        from utils.assert_utils import AssertUtils
        for validator in self.validate:
            #遍历断言列表，
            # 每个 validator 包含三要素： check （校验对象）、 assert_type （断言类型）、 expect （期望值）
            check_field = validator["check"]#从status_code,headers,body,jmespath里取出实际值
            assert_type = validator.get("assert_type", "eq")
            #断言类型，schema是一种，判断check取出的值是否合规
            expect = validator["expect"]#期望值

            # 特殊 check 字段：status_code / body / headers
            #根据check_field决定实际值从哪里取 ，actual是取出的值
            if check_field == "status_code":
                actual = resp.status_code
            elif check_field == "body":
                # 整个响应体，常用于 json_schema 校验
                actual = resp_json
            elif check_field == "headers":
                actual = dict(resp.headers)
            else:
                # jmespath 表达式从响应体提取字段
                try:
                    actual = runner.parser.extract_field(resp_json, check_field)
                except Exception:
                    actual = None

            AssertUtils.validate(actual, expect, assert_type)

        return {"name": self.name, "success": True, "attempts": None}
