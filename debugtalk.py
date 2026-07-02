import hashlib
import random
import string
import time
import uuid
#这里写入示例函数，允许在 YAML 中通过 ${get_token()} 调用自定义 Python 代码。
#生成随机的时间戳和签名计算

def get_token():
    """生成随机 Token，模拟登录态"""
    return f"token_{uuid.uuid4().hex}"


def gen_timestamp():
    """生成当前时间戳（秒）"""
    return int(time.time())


def gen_random_string(length=8):
    """生成指定长度的随机字符串（大小写字母+数字）

    Args:
        length: 字符串长度，默认 8
    """
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def sign(params):
    """简单签名计算：对参数字典按 key 排序后拼接并做 MD5签名计算

    Args:
        params: 参与签名的参数字典，如 {"id": 123, "name": "abc"}
    """
    # 按 key 字典序排序后拼接成 key=value&key=value
    sorted_items = sorted(params.items(), key=lambda x: str(x[0]))
    raw = "&".join(f"{k}={v}" for k, v in sorted_items)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def add(a, b):
    """加法运算，用于演示带参数的函数调用"""
    return a + b


def gen_user_id():
    """生成随机用户 ID（1000~9999）"""
    return random.randint(1000, 9999)
