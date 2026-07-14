import pytest
import allure


@pytest.mark.smoke
@pytest.mark.e2e
@pytest.mark.oms
@pytest.mark.pms
@pytest.mark.dataconsistency
@allure.feature("电商订单模块")
@allure.story("会员购物全链路")
@allure.title("会员购物下单全流程 E2E 测试")
@allure.description("测试链路：会员登录 -> 查询商品列表 -> 添加购物车 -> 生成订单 -> 查询订单详情")
@allure.severity(allure.severity_level.CRITICAL)
def test_mall_shopping_e2e(api_client, member_token):
    """电商购物全链路 E2E 测试

    测试链路：
    会员登录（fixture 完成） -> 查询商品列表获取商品ID -> 添加商品到购物车 -> 生成订单 -> 查询订单详情

    断言策略：
    - 每一步都断言 HTTP 状态码 = 200
    - 每一步都断言业务 code = 200
    - 最后一步断言订单状态 status = 0（待支付）
    """
    created_order_sn = None

    try:
        with allure.step("步骤1：查询商品列表，获取商品ID"):
            allure.attach("pageNum=1, pageSize=10", name="请求参数", attachment_type=allure.attachment_type.TEXT)

            resp = api_client.get("/pms/product/list", params={"pageNum": 1, "pageSize": 10})

            assert resp["status_code"] == 200, f"商品列表 HTTP 状态码异常: {resp['status_code']}"
            assert resp["code"] == 200, f"商品列表业务码异常: {resp['code']}, message: {resp['message']}"
            assert resp["data"] is not None, "商品列表 data 为空"
            assert "list" in resp["data"], "商品列表缺少 list 字段"
            assert len(resp["data"]["list"]) > 0, "商品列表为空"

            product = resp["data"]["list"][0]
            product_id = product["id"]
            product_name = product["name"]
            product_price = product["price"]
            product_stock = product["stock"]

            allure.attach(
                f"商品ID: {product_id}\n商品名称: {product_name}\n价格: {product_price}\n库存: {product_stock}",
                name="获取到的商品信息",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 获取到商品: id={product_id}, name={product_name}, price={product_price}, stock={product_stock}")

        with allure.step("步骤2：添加商品到购物车"):
            buy_quantity = 1
            allure.attach(
                f"商品ID: {product_id}\n数量: {buy_quantity}",
                name="加购参数",
                attachment_type=allure.attachment_type.TEXT
            )

            resp = api_client.post("/oms/cart/add", json_body={
                "product_id": product_id,
                "quantity": buy_quantity
            })

            assert resp["status_code"] == 200, f"添加购物车 HTTP 状态码异常: {resp['status_code']}"
            assert resp["code"] == 200, f"添加购物车业务码异常: {resp['code']}, message: {resp['message']}"
            assert resp["data"] is not None, "添加购物车 data 为空"
            assert resp["data"]["product_id"] == product_id, "购物车商品ID不匹配"
            assert resp["data"]["quantity"] == buy_quantity, "购物车商品数量不匹配"

            cart_item = resp["data"]
            allure.attach(
                f"购物车项ID: {cart_item['id']}\n商品ID: {cart_item['product_id']}\n数量: {cart_item['quantity']}",
                name="加购结果",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 已添加到购物车: product_id={cart_item['product_id']}, quantity={cart_item['quantity']}")

        with allure.step("步骤3：生成订单（下单）"):
            allure.attach(
                f"商品ID: {product_id}\n数量: {buy_quantity}\n收货人: 张三\n电话: 13800138000",
                name="下单参数",
                attachment_type=allure.attachment_type.TEXT
            )

            resp = api_client.post("/oms/order/generate", json_body={
                "product_id": product_id,
                "quantity": buy_quantity,
                "member_id": 1,
                "receiver_name": "张三",
                "receiver_phone": "13800138000",
                "receiver_detail_address": "北京市朝阳区xxx街道xxx号"
            })

            assert resp["status_code"] == 200, f"下单 HTTP 状态码异常: {resp['status_code']}"
            assert resp["code"] == 200, f"下单业务码异常: {resp['code']}, message: {resp['message']}"
            assert resp["data"] is not None, "下单响应 data 为空"
            assert "orderSn" in resp["data"], "下单响应缺少 orderSn 字段"
            assert "total_amount" in resp["data"], "下单响应缺少 total_amount 字段"

            created_order_sn = resp["data"]["orderSn"]
            total_amount = resp["data"]["total_amount"]

            allure.attach(created_order_sn, name="生成的订单号", attachment_type=allure.attachment_type.TEXT)
            allure.attach(str(total_amount), name="订单总金额", attachment_type=allure.attachment_type.TEXT)
            print(f"  ✅ 下单成功: orderSn={created_order_sn}, total_amount={total_amount}")

        with allure.step("步骤4：根据订单号查询订单详情（数据闭环断言）"):
            allure.attach(created_order_sn, name="查询的订单号", attachment_type=allure.attachment_type.TEXT)

            resp = api_client.get(f"/oms/order/detail/{created_order_sn}")

            assert resp["status_code"] == 200, f"订单详情 HTTP 状态码异常: {resp['status_code']}"
            assert resp["code"] == 200, f"订单详情业务码异常: {resp['code']}, message: {resp['message']}"
            assert resp["data"] is not None, "订单详情 data 为空"

            order_detail = resp["data"]

            assert order_detail["orderSn"] == created_order_sn, "订单号不匹配"
            assert order_detail["product_id"] == product_id, "订单商品ID不匹配"
            assert order_detail["quantity"] == buy_quantity, "订单商品数量不匹配"
            assert order_detail["status"] == 0, f"订单状态异常: 期望 0(待支付), 实际 {order_detail['status']}"
            assert order_detail["receiver_name"] == "张三", "收货人姓名不匹配"
            assert order_detail["receiver_phone"] == "13800138000", "收货人电话不匹配"

            allure.attach(
                f"订单号: {order_detail['orderSn']}\n"
                f"订单状态: {order_detail['status']} (0=待支付)\n"
                f"商品: {order_detail['product_name']} x {order_detail['quantity']}\n"
                f"收货人: {order_detail['receiver_name']}\n"
                f"下单时间: {order_detail['create_time']}",
                name="订单详情验证结果",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 订单详情验证通过:")
            print(f"     - 订单号: {order_detail['orderSn']}")
            print(f"     - 订单状态: {order_detail['status']} (0=待支付)")
            print(f"     - 商品: {order_detail['product_name']} x {order_detail['quantity']}")
            print(f"     - 收货人: {order_detail['receiver_name']}")
            print(f"     - 下单时间: {order_detail['create_time']}")

        print("\n" + "=" * 60)
        print("🎉 全链路测试通过！")
        print("=" * 60)

    finally:
        with allure.step("数据清理（Teardown）"):
            if created_order_sn:
                allure.attach(created_order_sn, name="待清理的订单号", attachment_type=allure.attachment_type.TEXT)
                print(f"\n🧹 [Teardown] 清理测试数据: 订单 {created_order_sn}")
                # ---- 伪代码开始 ----
                # 方式一：如果有删除订单接口
                # api_client.delete(f"/oms/order/{created_order_sn}")
                #
                # 方式二：调用 Mock 服务的重置接口（当前 Mock 服务已提供）
                # api_client.post("/reset")
                #
                # 方式三：直接修改数据库（仅测试环境）
                # db.execute("DELETE FROM orders WHERE order_sn = :sn", {"sn": created_order_sn})
                # ---- 伪代码结束 ----
                print(f"   (清理逻辑已预留，可根据实际接口实现)")


@pytest.mark.pms
@pytest.mark.api
@allure.feature("商品模块")
@allure.story("商品列表查询")
@allure.title("商品列表分页查询")
@allure.severity(allure.severity_level.NORMAL)
def test_product_list_pagination(api_client):
    """商品列表分页查询 - 单接口测试示例"""
    with allure.step("发送分页查询请求"):
        allure.attach("pageNum=1, pageSize=2", name="分页参数", attachment_type=allure.attachment_type.TEXT)
        resp = api_client.get("/pms/product/list", params={"pageNum": 1, "pageSize": 2})

    with allure.step("验证分页结果"):
        assert resp["status_code"] == 200
        assert resp["code"] == 200
        assert resp["data"]["total"] >= 3
        assert len(resp["data"]["list"]) == 2
        assert resp["data"]["pageNum"] == 1
        assert resp["data"]["pageSize"] == 2
        allure.attach(
            f"总数: {resp['data']['total']}\n当前页数量: {len(resp['data']['list'])}",
            name="分页验证结果",
            attachment_type=allure.attachment_type.TEXT
        )


@pytest.mark.exception
@pytest.mark.oms
@pytest.mark.api
@allure.feature("订单模块")
@allure.story("订单查询")
@allure.title("查询不存在的订单 - 异常场景")
@allure.severity(allure.severity_level.NORMAL)
def test_order_not_found(api_client, member_token):
    """查询不存在的订单 - 异常场景测试"""
    with allure.step("查询不存在的订单号"):
        fake_order_sn = "ORD_NOT_EXIST_123"
        allure.attach(fake_order_sn, name="查询的订单号", attachment_type=allure.attachment_type.TEXT)
        resp = api_client.get(f"/oms/order/detail/{fake_order_sn}")

    with allure.step("验证异常响应"):
        assert resp["status_code"] == 200
        assert resp["code"] == 404
        assert resp["message"] == "订单不存在"
        assert resp["data"] is None
        assert resp["success"] is False
        allure.attach(
            f"业务码: {resp['code']}\n消息: {resp['message']}",
            name="异常响应验证",
            attachment_type=allure.attachment_type.TEXT
        )
