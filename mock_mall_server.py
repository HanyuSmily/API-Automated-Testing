from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from fastapi import HTTPException
import uuid
import time
from datetime import datetime, timedelta

app = FastAPI(title="Mock Mall Server", description="轻量级 mall 电商系统 Mock 服务器")


# ==================== 内存数据库（状态保持核心） ====================

# 商品库存数据
products_db = [
    {
        "id": 1,
        "name": "华为 Mate 60 Pro",
        "price": 6999.00,
        "stock": 100,
        "brand": "华为",
        "category": "手机",
        "publish_status": 1,
        "delete_status": 0
    },
    {
        "id": 2,
        "name": "小米 14 Ultra",
        "price": 5999.00,
        "stock": 50,
        "brand": "小米",
        "category": "手机",
        "publish_status": 1,
        "delete_status": 0
    },
    {
        "id": 3,
        "name": "MacBook Pro 14",
        "price": 14999.00,
        "stock": 20,
        "brand": "苹果",
        "category": "电脑",
        "publish_status": 1,
        "delete_status": 0
    }
]

# 购物车数据
cart_db: List[dict] = []
CART_ITEM_MAX_QUANTITY = 99

# 订单数据
orders_db: List[dict] = []

# 管理员账号
admin_accounts = {
    "admin": "123456"
}

# 会员账号
member_accounts = {
    "testuser": "123456"
}

# 登录失败记录（用于账户锁定）
login_fail_count: dict = {}
LOCK_THRESHOLD = 5
LOCK_DURATION_SECONDS = 300
locked_accounts: dict = {}

# 优惠券数据
coupons_db: List[dict] = []
member_coupons_db: List[dict] = []

# 幂等性记录（防止重复下单）
idempotency_keys: dict = {}


# ==================== 统一响应格式工具 ====================

def success_response(data=None, message="操作成功"):
    return {
        "code": 200,
        "message": message,
        "data": data
    }


def fail_response(message="操作失败", code=500, data=None):
    return {
        "code": code,
        "message": message,
        "data": data
    }


# ==================== 工具函数 ====================

def is_account_locked(username: str) -> bool:
    """检查账户是否被锁定"""
    if username in locked_accounts:
        lock_time = locked_accounts[username]
        if time.time() - lock_time < LOCK_DURATION_SECONDS:
            return True
        else:
            del locked_accounts[username]
            login_fail_count[username] = 0
    return False


def record_login_failure(username: str):
    """记录登录失败次数，达到阈值则锁定账户"""
    if username not in login_fail_count:
        login_fail_count[username] = 0
    login_fail_count[username] += 1
    if login_fail_count[username] >= LOCK_THRESHOLD:
        locked_accounts[username] = time.time()


def get_product_by_id(product_id: int):
    """根据ID获取商品"""
    for p in products_db:
        if p["id"] == product_id:
            return p
    return None


def get_product_index(product_id: int) -> int:
    """根据ID获取商品索引"""
    for idx, p in enumerate(products_db):
        if p["id"] == product_id:
            return idx
    return -1


def get_order_by_sn(order_sn: str):
    """根据订单号获取订单"""
    for o in orders_db:
        if o["orderSn"] == order_sn:
            return o
    return None


def get_coupon_by_id(coupon_id: int):
    """根据ID获取优惠券"""
    for c in coupons_db:
        if c["id"] == coupon_id:
            return c
    return None


def get_member_coupon(member_id: int, coupon_id: int):
    """获取会员的某张优惠券记录"""
    for mc in member_coupons_db:
        if mc["member_id"] == member_id and mc["coupon_id"] == coupon_id:
            return mc
    return None


def count_member_coupons(member_id: int, coupon_id: int) -> int:
    """统计会员领取某优惠券的数量"""
    return sum(1 for mc in member_coupons_db
               if mc["member_id"] == member_id and mc["coupon_id"] == coupon_id)


# ==================== Pydantic 请求模型 ====================

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class MemberLoginRequest(BaseModel):
    username: str
    password: str


class CartAddRequest(BaseModel):
    product_id: int
    quantity: int = 1


class OrderGenerateRequest(BaseModel):
    product_id: int
    quantity: int
    member_id: Optional[int] = 1
    receiver_name: Optional[str] = "张三"
    receiver_phone: Optional[str] = "13800138000"
    receiver_detail_address: Optional[str] = "北京市朝阳区xxx街道xxx号"
    coupon_id: Optional[int] = None
    idempotency_key: Optional[str] = None
    expected_amount: Optional[float] = None


class CouponCreateRequest(BaseModel):
    name: str
    type: int = 0
    platform: int = 0
    amount: float
    min_point: float
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    use_type: int = 0
    note: Optional[str] = ""
    publish_count: int = 100
    per_limit: int = 1


class CouponReceiveRequest(BaseModel):
    coupon_id: int


class ProductCreateRequest(BaseModel):
    name: str
    price: float
    stock: int = 100
    brand: Optional[str] = ""
    category: Optional[str] = ""


class OrderPayRequest(BaseModel):
    order_sn: str


class OrderDeliveryRequest(BaseModel):
    order_sn: str
    delivery_company: Optional[str] = "顺丰速运"
    delivery_sn: Optional[str] = None


class OrderCloseRequest(BaseModel):
    order_sn: str
    note: Optional[str] = ""


# ==================== Admin 端接口 ====================

@app.post("/admin/login")
def admin_login(req: AdminLoginRequest):
    """管理员登录接口"""
    username = req.username
    password = req.password

    if is_account_locked(f"admin_{username}"):
        return fail_response(message="账户已被锁定，请稍后再试", code=423)

    if username not in admin_accounts:
        record_login_failure(f"admin_{username}")
        return fail_response(message="账号不存在", code=401)

    if admin_accounts[username] != password:
        record_login_failure(f"admin_{username}")
        fail_count = login_fail_count.get(f"admin_{username}", 0)
        remain = LOCK_THRESHOLD - fail_count
        return fail_response(
            message=f"密码错误，剩余尝试次数：{remain}" if remain > 0 else "密码错误次数过多，账户已锁定",
            code=401
        )

    login_fail_count[f"admin_{username}"] = 0
    token = f"mock-admin-token-{uuid.uuid4().hex[:12]}"
    return success_response(data={
        "token": token,
        "tokenHead": "Bearer "
    }, message="登录成功")


@app.post("/admin/pms/product/create")
def admin_create_product(req: ProductCreateRequest):
    """Admin端：创建/发布新商品"""
    new_id = max([p["id"] for p in products_db]) + 1 if products_db else 1
    new_product = {
        "id": new_id,
        "name": req.name,
        "price": req.price,
        "stock": req.stock,
        "brand": req.brand,
        "category": req.category,
        "publish_status": 1,
        "delete_status": 0
    }
    products_db.append(new_product)
    return success_response(data=new_product, message="商品创建成功")


@app.post("/admin/oms/order/pay")
def admin_order_pay(req: OrderPayRequest):
    """Admin端：模拟支付回调，更新订单状态为待发货"""
    order = get_order_by_sn(req.order_sn)
    if not order:
        return fail_response(message="订单不存在", code=404)

    if order["status"] != 0:
        return fail_response(message=f"订单状态不支持支付操作，当前状态：{order['status']}", code=400)

    order["status"] = 1
    order["payment_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return success_response(data={"orderSn": order["orderSn"], "status": 1}, message="支付成功")


@app.post("/admin/oms/order/delivery")
def admin_order_delivery(req: OrderDeliveryRequest):
    """Admin端：发货，更新订单状态为已发货"""
    order = get_order_by_sn(req.order_sn)
    if not order:
        return fail_response(message="订单不存在", code=404)

    if order["status"] != 1:
        return fail_response(message=f"订单状态不支持发货操作，当前状态：{order['status']}", code=400)

    order["status"] = 2
    order["delivery_company"] = req.delivery_company
    order["delivery_sn"] = req.delivery_sn or f"SF{uuid.uuid4().hex[:10].upper()}"
    order["delivery_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return success_response(data={"orderSn": order["orderSn"], "status": 2}, message="发货成功")


@app.post("/admin/oms/order/close")
def admin_order_close(req: OrderCloseRequest):
    """Admin端：关闭订单，释放库存"""
    order = get_order_by_sn(req.order_sn)
    if not order:
        return fail_response(message="订单不存在", code=404)

    if order["status"] in (3, 4):
        return fail_response(message=f"订单已完成或已关闭，不能重复操作，当前状态：{order['status']}", code=400)

    product_idx = get_product_index(order["product_id"])
    if product_idx >= 0:
        products_db[product_idx]["stock"] += order["quantity"]

    order["status"] = 4
    order["close_note"] = req.note
    order["close_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

    if order.get("coupon_id"):
        mc = get_member_coupon(order["member_id"], order["coupon_id"])
        if mc and mc["status"] == 1:
            mc["status"] = 0
            mc["use_order_sn"] = None
            mc["use_time"] = None

    return success_response(data={"orderSn": order["orderSn"], "status": 4}, message="订单已关闭")


@app.post("/admin/sms/coupon/create")
def admin_create_coupon(req: CouponCreateRequest):
    """Admin端：创建优惠券"""
    new_id = max([c["id"] for c in coupons_db]) + 1 if coupons_db else 1
    now = datetime.now()

    coupon = {
        "id": new_id,
        "name": req.name,
        "type": req.type,
        "platform": req.platform,
        "amount": req.amount,
        "min_point": req.min_point,
        "start_time": req.start_time or now.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": req.end_time or (now + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"),
        "use_type": req.use_type,
        "note": req.note,
        "publish_count": req.publish_count,
        "use_count": 0,
        "receive_count": 0,
        "per_limit": req.per_limit,
        "status": 0
    }
    coupons_db.append(coupon)
    return success_response(data=coupon, message="优惠券创建成功")


@app.get("/admin/sms/coupon/list")
def admin_coupon_list():
    """Admin端：查询优惠券列表"""
    return success_response(data={"list": coupons_db, "total": len(coupons_db)})


# ==================== Portal 端接口 ====================

@app.post("/sso/login")
def member_login(req: MemberLoginRequest):
    """会员登录接口"""
    username = req.username
    password = req.password

    if is_account_locked(f"member_{username}"):
        return fail_response(message="账户已被锁定，请5分钟后再试", code=423)

    if username not in member_accounts:
        record_login_failure(f"member_{username}")
        return fail_response(message="账号不存在", code=401)

    if member_accounts[username] != password:
        record_login_failure(f"member_{username}")
        fail_count = login_fail_count.get(f"member_{username}", 0)
        remain = LOCK_THRESHOLD - fail_count
        return fail_response(
            message=f"密码错误，剩余尝试次数：{remain}" if remain > 0 else "密码错误次数过多，账户已锁定",
            code=401
        )

    login_fail_count[f"member_{username}"] = 0
    token = f"mock-member-token-{uuid.uuid4().hex[:12]}"
    return success_response(data={
        "token": token,
        "tokenHead": "Bearer "
    }, message="登录成功")


@app.get("/pms/product/list")
def product_list(
    pageNum: str = "1",
    pageSize: str = "10",
    keyword: Optional[str] = None
):
    """商品列表查询接口（支持边界/异常场景）"""
    try:
        page_num = int(pageNum)
    except (ValueError, TypeError):
        return fail_response(message="参数非法：pageNum 必须为整数", code=400)

    try:
        page_size = int(pageSize)
    except (ValueError, TypeError):
        return fail_response(message="参数非法：pageSize 必须为整数", code=400)

    if page_num <= 0:
        page_num = 1

    if page_size == 0:
        return success_response(data={
            "list": [],
            "total": len(products_db),
            "pageNum": page_num,
            "pageSize": 0,
            "totalPage": 0
        })

    if page_size > 100:
        page_size = 100

    result = [p for p in products_db if p.get("delete_status", 0) == 0]

    if keyword:
        result = [p for p in result if keyword.lower() in p["name"].lower()]

    total = len(result)
    start = (page_num - 1) * page_size
    end = start + page_size
    page_data = result[start:end]

    return success_response(data={
        "list": page_data,
        "total": total,
        "pageNum": page_num,
        "pageSize": page_size,
        "totalPage": (total + page_size - 1) // page_size if page_size > 0 else 0
    })


@app.get("/pms/product/detail/{product_id}")
def product_detail(product_id: int):
    """商品详情查询接口"""
    product = get_product_by_id(product_id)
    if not product:
        return fail_response(message="商品不存在", code=404)
    if product.get("publish_status", 1) != 1:
        return fail_response(message="商品已下架", code=404)
    return success_response(data=product)


@app.post("/oms/cart/add")
def cart_add(req: CartAddRequest):
    """添加购物车接口（支持边界/异常场景）"""
    product_id = req.product_id
    quantity = req.quantity

    product = get_product_by_id(product_id)

    if not product:
        return fail_response(message="商品不存在", code=404)

    if product.get("publish_status", 1) != 1:
        return fail_response(message="商品已下架，无法加入购物车", code=400)

    if product.get("stock", 0) <= 0:
        return fail_response(message="商品库存不足", code=400)

    if quantity <= 0:
        return fail_response(message="商品数量必须大于0", code=400)

    if quantity > CART_ITEM_MAX_QUANTITY:
        return fail_response(
            message=f"购物车单品数量不能超过{CART_ITEM_MAX_QUANTITY}件",
            code=400
        )

    if quantity > product["stock"]:
        return fail_response(
            message=f"库存不足，当前库存：{product['stock']}",
            code=400
        )

    existing_idx = -1
    for idx, item in enumerate(cart_db):
        if item["product_id"] == product_id and item["member_id"] == 1:
            existing_idx = idx
            break

    if existing_idx >= 0:
        new_qty = cart_db[existing_idx]["quantity"] + quantity
        if new_qty > CART_ITEM_MAX_QUANTITY:
            return fail_response(
                message=f"购物车单品数量不能超过{CART_ITEM_MAX_QUANTITY}件",
                code=400
            )
        if new_qty > product["stock"]:
            return fail_response(
                message=f"库存不足，当前库存：{product['stock']}",
                code=400
            )
        cart_db[existing_idx]["quantity"] = new_qty
        return success_response(data=cart_db[existing_idx], message="购物车数量已更新")

    cart_item = {
        "id": len(cart_db) + 1,
        "product_id": product_id,
        "product_name": product["name"],
        "product_price": product["price"],
        "quantity": quantity,
        "member_id": 1,
        "create_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    cart_db.append(cart_item)

    return success_response(data=cart_item, message="添加购物车成功")


@app.get("/oms/cart/list")
def cart_list(member_id: int = 1):
    """购物车列表查询接口"""
    member_cart = [item for item in cart_db if item["member_id"] == member_id]
    return success_response(data={
        "list": member_cart,
        "total": len(member_cart)
    })


@app.post("/oms/order/generate")
def order_generate(req: OrderGenerateRequest):
    """生成订单（下单）接口 - 支持优惠券核销、幂等性、金额校验"""
    product_id = req.product_id
    quantity = req.quantity

    if req.idempotency_key:
        if req.idempotency_key in idempotency_keys:
            cached_order_sn = idempotency_keys[req.idempotency_key]
            cached_order = get_order_by_sn(cached_order_sn)
            if cached_order:
                return success_response(data={
                    "orderSn": cached_order_sn,
                    "total_amount": cached_order["total_amount"],
                    "pay_amount": cached_order["pay_amount"],
                    "freight_amount": cached_order["freight_amount"],
                    "is_idempotent": True
                }, message="重复请求，订单已存在")

    product = get_product_by_id(product_id)
    product_index = get_product_index(product_id)

    if not product:
        return fail_response(message="商品不存在", code=404)

    if product.get("publish_status", 1) != 1:
        return fail_response(message="商品已下架", code=400)

    if quantity <= 0:
        return fail_response(message="商品数量必须大于0", code=400)

    if quantity > product["stock"]:
        return fail_response(message=f"库存不足，当前库存：{product['stock']}", code=400)

    total_amount = product["price"] * quantity
    freight_amount = 0
    discount_amount = 0
    coupon_id = req.coupon_id
    used_coupon = None

    if coupon_id is not None:
        coupon = get_coupon_by_id(coupon_id)
        if not coupon:
            return fail_response(message="优惠券不存在", code=400)

        mc = get_member_coupon(req.member_id, coupon_id)
        if not mc:
            return fail_response(message="您未领取该优惠券", code=400)
        if mc["status"] != 0:
            return fail_response(message="优惠券状态不可用", code=400)

        now = datetime.now()
        end_time = datetime.strptime(coupon["end_time"], "%Y-%m-%d %H:%M:%S")
        start_time = datetime.strptime(coupon["start_time"], "%Y-%m-%d %H:%M:%S")
        if now < start_time:
            return fail_response(message="优惠券尚未开始生效", code=400)
        if now > end_time:
            return fail_response(message="优惠券已过期", code=400)

        if total_amount < coupon["min_point"]:
            return fail_response(
                message=f"未达到优惠券使用门槛，最低消费：{coupon['min_point']}元",
                code=400
            )

        discount_amount = coupon["amount"]
        used_coupon = mc

    pay_amount = total_amount - discount_amount + freight_amount
    if pay_amount < 0:
        pay_amount = 0

    if req.expected_amount is not None:
        if abs(req.expected_amount - pay_amount) > 0.01:
            return fail_response(
                message=f"结算金额不一致，后端计算：{pay_amount}，前端传入：{req.expected_amount}",
                code=400
            )

    products_db[product_index]["stock"] -= quantity

    order_sn = f"ORD{int(time.time() * 1000)}{uuid.uuid4().hex[:4].upper()}"

    order = {
        "orderSn": order_sn,
        "product_id": product_id,
        "product_name": product["name"],
        "product_price": product["price"],
        "quantity": quantity,
        "total_amount": total_amount,
        "pay_amount": pay_amount,
        "freight_amount": freight_amount,
        "discount_amount": discount_amount,
        "coupon_id": coupon_id,
        "status": 0,
        "member_id": req.member_id,
        "receiver_name": req.receiver_name,
        "receiver_phone": req.receiver_phone,
        "receiver_detail_address": req.receiver_detail_address,
        "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "payment_time": None,
        "delivery_time": None,
        "receive_time": None,
        "comment_time": None
    }

    orders_db.append(order)

    if used_coupon:
        used_coupon["status"] = 1
        used_coupon["use_order_sn"] = order_sn
        used_coupon["use_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        coupon_db = get_coupon_by_id(coupon_id)
        if coupon_db:
            coupon_db["use_count"] += 1

    if req.idempotency_key:
        idempotency_keys[req.idempotency_key] = order_sn

    return success_response(data={
        "orderSn": order_sn,
        "total_amount": total_amount,
        "pay_amount": pay_amount,
        "freight_amount": freight_amount,
        "discount_amount": discount_amount
    }, message="下单成功")


@app.get("/oms/order/detail/{orderSn}")
def order_detail(orderSn: str):
    """订单详情查询接口"""
    order = get_order_by_sn(orderSn)
    if order:
        return success_response(data=order, message="查询成功")
    return fail_response(message="订单不存在", code=404)


@app.get("/oms/order/list")
def order_list(member_id: int = 1, status: Optional[int] = None):
    """订单列表查询接口"""
    member_orders = [o for o in orders_db if o["member_id"] == member_id]

    if status is not None:
        member_orders = [o for o in member_orders if o["status"] == status]

    member_orders.sort(key=lambda x: x["create_time"], reverse=True)

    return success_response(data={
        "list": member_orders,
        "total": len(member_orders)
    })


@app.post("/oms/order/confirmReceive/{orderSn}")
def order_confirm_receive(orderSn: str):
    """Portal端：会员确认收货"""
    order = get_order_by_sn(orderSn)
    if not order:
        return fail_response(message="订单不存在", code=404)

    if order["status"] != 2:
        return fail_response(message=f"订单状态不支持确认收货，当前状态：{order['status']}", code=400)

    order["status"] = 3
    order["receive_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return success_response(data={"orderSn": orderSn, "status": 3}, message="确认收货成功")


# ==================== SMS 优惠券模块接口 ====================

@app.get("/sms/coupon/list")
def coupon_list():
    """优惠券列表（可领取）"""
    available = [c for c in coupons_db if c["status"] == 0
                 and c["receive_count"] < c["publish_count"]]
    return success_response(data={"list": available, "total": len(available)})


@app.post("/sms/coupon/receive")
def coupon_receive(req: CouponReceiveRequest, member_id: int = 1):
    """会员领取优惠券"""
    coupon = get_coupon_by_id(req.coupon_id)
    if not coupon:
        return fail_response(message="优惠券不存在", code=404)

    if coupon["status"] != 0:
        return fail_response(message="优惠券已下架", code=400)

    now = datetime.now()
    end_time = datetime.strptime(coupon["end_time"], "%Y-%m-%d %H:%M:%S")
    start_time = datetime.strptime(coupon["start_time"], "%Y-%m-%d %H:%M:%S")
    if now < start_time:
        return fail_response(message="优惠券尚未开始领取", code=400)
    if now > end_time:
        return fail_response(message="优惠券已过期", code=400)

    if coupon["receive_count"] >= coupon["publish_count"]:
        return fail_response(message="优惠券已被领完", code=400)

    received = count_member_coupons(member_id, req.coupon_id)
    if received >= coupon["per_limit"]:
        return fail_response(
            message=f"每人限领{coupon['per_limit']}张，您已领取{received}张",
            code=400
        )

    coupon["receive_count"] += 1
    member_coupon = {
        "id": len(member_coupons_db) + 1,
        "member_id": member_id,
        "coupon_id": req.coupon_id,
        "coupon_name": coupon["name"],
        "amount": coupon["amount"],
        "min_point": coupon["min_point"],
        "start_time": coupon["start_time"],
        "end_time": coupon["end_time"],
        "status": 0,
        "use_order_sn": None,
        "use_time": None,
        "receive_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    member_coupons_db.append(member_coupon)

    return success_response(data=member_coupon, message="领取成功")


@app.get("/sms/coupon/mine")
def my_coupons(member_id: int = 1, status: Optional[int] = None):
    """我的优惠券列表"""
    mine = [mc for mc in member_coupons_db if mc["member_id"] == member_id]
    if status is not None:
        mine = [mc for mc in mine if mc["status"] == status]
    return success_response(data={"list": mine, "total": len(mine)})


# ==================== 辅助接口（测试用） ====================

@app.get("/health")
def health_check():
    """健康检查接口"""
    return success_response(data={"status": "ok", "timestamp": time.time()})


@app.post("/reset")
def reset_data():
    """重置所有数据（测试辅助）"""
    global cart_db, orders_db, products_db, coupons_db, member_coupons_db
    global login_fail_count, locked_accounts, idempotency_keys

    cart_db.clear()
    orders_db.clear()
    coupons_db.clear()
    member_coupons_db.clear()
    login_fail_count.clear()
    locked_accounts.clear()
    idempotency_keys.clear()

    for p in products_db:
        if p["id"] == 1:
            p["stock"] = 100
        elif p["id"] == 2:
            p["stock"] = 50
        elif p["id"] == 3:
            p["stock"] = 20
        p["publish_status"] = 1
        p["delete_status"] = 0

    return success_response(data=None, message="数据已重置")


@app.get("/debug/products")
def debug_products():
    """调试：查看商品库存状态"""
    return success_response(data=products_db)


@app.get("/debug/orders")
def debug_orders():
    """调试：查看所有订单"""
    return success_response(data=orders_db)


@app.get("/debug/cart")
def debug_cart():
    """调试：查看购物车"""
    return success_response(data=cart_db)


@app.get("/debug/coupons")
def debug_coupons():
    """调试：查看优惠券"""
    return success_response(data={"coupons": coupons_db, "member_coupons": member_coupons_db})


@app.get("/debug/reset-lock/{username}")
def debug_reset_lock(username: str, account_type: str = "member"):
    """调试：重置账户锁定状态"""
    key = f"{account_type}_{username}"
    if key in login_fail_count:
        login_fail_count[key] = 0
    if key in locked_accounts:
        del locked_accounts[key]
    return success_response(message="账户锁定状态已重置")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
