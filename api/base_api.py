import json
import requests
from typing import Optional, Dict, Any, Union
from loguru import logger

try:
    import allure
    from allure import attachment_type
    _ALLURE_AVAILABLE = True
except ImportError:
    _ALLURE_AVAILABLE = False
    attachment_type = None


class BaseAPI:
    """基于 requests.Session 封装的统一 API 请求客户端

    核心特性：
    - 会话复用：基于 requests.Session，自动管理 Cookie/连接池
    - 统一格式：所有请求返回统一的响应对象，自动解析 JSON
    - 失败留证：请求失败时自动打印请求/响应详情，预留 allure.attach 接口
    - 令牌注入：支持设置全局 Authorization 头
    """

    def __init__(self, base_url: str = "", timeout: int = 30):
        """初始化 API 客户端

        Args:
            base_url: 基础 URL，所有请求路径会自动拼接
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self._token: Optional[str] = None
        self._token_head: str = "Bearer "

    def set_token(self, token: str, token_head: str = "Bearer "):
        """设置认证令牌

        Args:
            token: 令牌字符串
            token_head: 令牌前缀，默认 "Bearer "
        """
        self._token = token
        self._token_head = token_head
        if token:
            self.session.headers["Authorization"] = f"{token_head}{token}"
        else:
            self.session.headers.pop("Authorization", None)

    def _build_url(self, path: str) -> str:
        """拼接完整 URL

        Args:
            path: 请求路径

        Returns:
            完整的 URL
        """
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _attach_allure(self, name: str, body: str, attachment_type_enum=None):
        """Allure 附件记录接口

        Args:
            name: 附件名称
            body: 附件内容
            attachment_type_enum: allure.attachment_type 枚举值
        """
        if _ALLURE_AVAILABLE:
            try:
                if attachment_type_enum:
                    allure.attach(body, name=name, attachment_type=attachment_type_enum)
                else:
                    allure.attach(body, name=name, attachment_type=allure.attachment_type.TEXT)
            except Exception:
                pass

    def _log_failure(self, method: str, url: str,
                     headers: Dict, params: Optional[Dict],
                     body: Optional[Any], response: Optional[requests.Response],
                     exception: Optional[Exception] = None):
        """失败留证：记录请求/响应详情

        Args:
            method: HTTP 方法
            url: 请求 URL
            headers: 请求头
            params: URL 参数
            body: 请求体
            response: 响应对象（可能为 None）
            exception: 异常对象（可能为 None）
        """
        separator = "=" * 60
        logger.error(f"\n{separator}\n"
                     f"⚠️  请求失败详情\n"
                     f"{separator}")
        logger.error(f"Method: {method}")
        logger.error(f"URL: {url}")

        if params:
            logger.error(f"Params: {json.dumps(params, ensure_ascii=False, indent=2)}")

        safe_headers = {k: v for k, v in headers.items()
                        if k.lower() not in ("authorization", "cookie")}
        logger.error(f"Headers (脱敏): {json.dumps(safe_headers, ensure_ascii=False, indent=2)}")

        if body is not None:
            if isinstance(body, (dict, list)):
                body_str = json.dumps(body, ensure_ascii=False, indent=2)
            else:
                body_str = str(body)
            logger.error(f"Request Body:\n{body_str}")

        if exception:
            logger.error(f"Exception Type: {type(exception).__name__}")
            logger.error(f"Exception Message: {str(exception)}")

        if response is not None:
            logger.error(f"Status Code: {response.status_code}")
            logger.error(f"Response Headers: {json.dumps(dict(response.headers), ensure_ascii=False, indent=2)}")
            try:
                resp_body = response.text
                if len(resp_body) > 2000:
                    resp_body_display = resp_body[:2000] + "\n... (已截断)"
                else:
                    resp_body_display = resp_body
                logger.error(f"Response Body:\n{resp_body_display}")
            except Exception:
                resp_body = ""
                logger.error(f"Response Body: <无法解析>")

            request_info = {
                "method": method,
                "url": url,
                "params": params,
                "headers": safe_headers,
                "body": body
            }
            self._attach_allure(
                "请求信息",
                json.dumps(request_info, ensure_ascii=False, indent=2),
                allure.attachment_type.JSON if _ALLURE_AVAILABLE else None
            )

            response_info = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": resp_body
            }
            self._attach_allure(
                "响应信息",
                json.dumps(response_info, ensure_ascii=False, indent=2),
                allure.attachment_type.JSON if _ALLURE_AVAILABLE else None
            )
        else:
            request_info = {
                "method": method,
                "url": url,
                "params": params,
                "headers": safe_headers,
                "body": body,
                "exception": {
                    "type": type(exception).__name__ if exception else None,
                    "message": str(exception) if exception else None
                }
            }
            self._attach_allure(
                "请求失败信息",
                json.dumps(request_info, ensure_ascii=False, indent=2),
                allure.attachment_type.JSON if _ALLURE_AVAILABLE else None
            )

        logger.error(separator)

    def request(self, method: str, path: str,
                params: Optional[Dict] = None,
                json_body: Optional[Any] = None,
                data: Optional[Any] = None,
                headers: Optional[Dict] = None,
                **kwargs) -> Dict[str, Any]:
        """统一请求方法

        Args:
            method: HTTP 方法（GET/POST/PUT/DELETE 等）
            path: 请求路径（或完整 URL）
            params: URL 查询参数
            json_body: JSON 请求体
            data: 表单数据
            headers: 额外请求头
            **kwargs: 其他传递给 requests 的参数

        Returns:
            统一格式的字典：{success, status_code, data, code, message, raw}
                - success: bool，HTTP 200 且业务 code=200 时为 True
                - status_code: int，HTTP 状态码
                - data: 响应 JSON 的 data 字段（可能为 None）
                - code: 业务状态码（可能为 None）
                - message: 业务消息（可能为 None）
                - raw: 原始 requests.Response 对象
        """
        url = self._build_url(path)
        method = method.upper()

        req_headers = dict(self.session.headers)
        if headers:
            req_headers.update(headers)

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                data=data,
                headers=headers,
                timeout=self.timeout,
                **kwargs
            )
        except Exception as e:
            self._log_failure(method, url, req_headers, params, json_body or data, None, e)
            return {
                "success": False,
                "status_code": 0,
                "data": None,
                "code": None,
                "message": f"请求异常: {type(e).__name__}: {str(e)}",
                "raw": None
            }

        try:
            resp_json = response.json()
        except Exception:
            resp_json = None

        business_code = resp_json.get("code") if isinstance(resp_json, dict) else None
        business_message = resp_json.get("message") if isinstance(resp_json, dict) else None
        business_data = resp_json.get("data") if isinstance(resp_json, dict) else None

        http_ok = 200 <= response.status_code < 300
        business_ok = (business_code == 200) if business_code is not None else http_ok
        success = http_ok and business_ok

        if not success:
            self._log_failure(method, url, req_headers, params, json_body or data, response)

        return {
            "success": success,
            "status_code": response.status_code,
            "data": business_data,
            "code": business_code,
            "message": business_message,
            "raw": response
        }

    def get(self, path: str, params: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """GET 请求快捷方法"""
        return self.request("GET", path, params=params, **kwargs)

    def post(self, path: str, json_body: Optional[Any] = None,
             data: Optional[Any] = None, params: Optional[Dict] = None,
             **kwargs) -> Dict[str, Any]:
        """POST 请求快捷方法"""
        return self.request("POST", path, params=params, json_body=json_body, data=data, **kwargs)

    def put(self, path: str, json_body: Optional[Any] = None,
            params: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """PUT 请求快捷方法"""
        return self.request("PUT", path, params=params, json_body=json_body, **kwargs)

    def delete(self, path: str, params: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """DELETE 请求快捷方法"""
        return self.request("DELETE", path, params=params, **kwargs)
