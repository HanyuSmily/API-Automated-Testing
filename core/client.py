import requests
import time
from loguru import logger

#client.py的核心作用是对底层的 HTTP 请求库（如 requests）进行封装，
# 使其更符合测试需求：不仅要发送请求，还要记录请求耗时、状态、响应内容，以便后续断言和分析。

class HttpSession(requests.Session):
    """
    HTTP 会话客户端：自动处理 Cookie，记录每个请求的统计信息
    """

    def __init__(self):
        super().__init__()
        # 设置默认超时时间，避免接口卡死导致测试流程挂起
        self.timeout = 120

    def request(self, method, url, **kwargs):
        """
        重写 request 方法，在发送请求前后增加日志记录
        """
        # kwargs.setdefault 关键字参数调用方法，
        # 确保如果用户没有传 timeout，就使用默认值 120 秒
        kwargs.setdefault("timeout", self.timeout)

        # 1. 记录开始时间，用于计算接口响应速度
        start_at = time.time()

        # 2. 打印请求日志，方便在终端查看测试进度
        logger.info(f"发送请求: {method} {url}")

        # 3. 调用父类 requests.Session 的 request 方法真正发出 HTTP 请求
        response = super().request(method, url, **kwargs)

        # 4. 计算耗时：结束时间减去开始时间，单位转换成毫秒 (ms)
        elapsed_ms = round((time.time() - start_at) * 1000, 2)

        # 5. 记录响应的关键指标
        logger.info(f"响应状态码: {response.status_code}, 耗时: {elapsed_ms}ms")

        # 6. 异常检查：如果状态码是 4xx 或 5xx，触发 raise_for_status 抛出异常
        try:
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"请求发生异常: {e}")

        return response