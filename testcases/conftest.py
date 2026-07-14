import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.base_api import BaseAPI
from core.env_manager import get_env_manager

_env_mgr = get_env_manager()

BASE_URL = _env_mgr.base_url


@pytest.fixture(scope="session")
def base_url():
    """全局 base_url fixture（从 env.yml 读取当前环境配置）"""
    return BASE_URL


@pytest.fixture(scope="session")
def env_manager():
    """环境管理器 fixture"""
    return _env_mgr


@pytest.fixture(scope="session")
def api_client(base_url):
    """全局 API 客户端 fixture"""
    timeout = _env_mgr.request_timeout
    client = BaseAPI(base_url=base_url, timeout=timeout)
    return client


@pytest.fixture(scope="function")
def member_token(api_client):
    """会员登录 fixture - 返回 token 字符串

    测试开始前自动调用前台登录接口，获取 Token 并返回。
    账号从 env.yml 的当前环境配置中读取。
    scope=function 表示每个测试函数执行前都会重新登录，避免状态污染。
    """
    account = _env_mgr.member_account
    username = account.get("username", "testuser")
    password = account.get("password", "123456")

    resp = api_client.post("/sso/login", json_body={
        "username": username,
        "password": password
    })

    assert resp["status_code"] == 200, f"登录 HTTP 状态码异常: {resp['status_code']}"
    assert resp["code"] == 200, f"登录业务码异常: {resp['code']}, message: {resp['message']}"
    assert resp["data"] is not None, "登录响应 data 为空"
    assert "token" in resp["data"], "登录响应缺少 token 字段"

    token = resp["data"]["token"]
    token_head = resp["data"].get("tokenHead", "Bearer ")

    api_client.set_token(token, token_head)

    yield token

    api_client.set_token("")


@pytest.fixture(scope="function")
def admin_token(api_client):
    """管理员登录 fixture - 返回 admin token 字符串

    账号从 env.yml 的当前环境配置中读取。
    """
    account = _env_mgr.admin_account
    username = account.get("username", "admin")
    password = account.get("password", "123456")

    resp = api_client.post("/admin/login", json_body={
        "username": username,
        "password": password
    })

    assert resp["status_code"] == 200, f"管理员登录 HTTP 状态码异常: {resp['status_code']}"
    assert resp["code"] == 200, f"管理员登录业务码异常: {resp['code']}, message: {resp['message']}"
    assert resp["data"] is not None, "管理员登录响应 data 为空"
    assert "token" in resp["data"], "管理员登录响应缺少 token 字段"

    token = resp["data"]["token"]
    token_head = resp["data"].get("tokenHead", "Bearer ")

    api_client.set_token(token, token_head)

    yield token

    api_client.set_token("")
