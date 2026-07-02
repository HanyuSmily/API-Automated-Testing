from core.client import HttpSession

# 1. 初始化会话
session = HttpSession()

# 2. 发送请求：测试框架会自动在终端打印出请求信息和耗时
resp = session.get("https://httpbin.org/get")

# 3. 校验结果
assert resp.status_code == 200
print(f"接口返回的 JSON 内容: {resp.json()}")