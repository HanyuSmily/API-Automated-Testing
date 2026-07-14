import pytest
import allure


@pytest.mark.smoke
@pytest.mark.e2e
@pytest.mark.oms
@pytest.mark.refund
@pytest.mark.dataconsistency
@allure.feature("订单模块-OMS")
@allure.story("超时未支付与订单关闭逆向链路")
@allure.title("订单关闭-库存回滚全流程 E2E 测试")
@allure.description("测试链路：会员下单锁定库存 -> Admin 关闭订单 -> 校验订单状态 -> 校验库存已回滚")
@allure.severity(allure.severity_level.CRITICAL)
def test_order_close_stock_rollback_e2e(api_client, member_token, admin_token):
    """超时未支付与逆向退款链路 E2E 测试（链路 C）

    场景：
    1. Portal 端会员下单，锁定库存 1 件，单据进入待支付状态（status=0）
    2. Admin 端后台触发订单关闭，状态变更为 4（已关闭）
    3. 数据断言：
       - 订单状态变更为 4（已关闭）
       - 之前被锁定的商品库存自动回滚释放，库存恢复原值
    """
    created_order_sn = None
    initial_stock = None
    product_id = None
    buy_quantity = 1

    try:
        with allure.step("步骤1：查询商品，记录初始库存"):
            resp = api_client.get("/pms/product/list", params={"pageNum": 1, "pageSize": 10})
            assert resp["status_code"] == 200
            assert resp["code"] == 200

            product = resp["data"]["list"][0]
            product_id = product["id"]
            product_name = product["name"]
            initial_stock = product["stock"]

            allure.attach(
                f"商品ID: {product_id}\n商品名: {product_name}\n初始库存: {initial_stock}",
                name="初始商品信息",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 选择商品: {product_name}, 初始库存={initial_stock}")

        with allure.step("步骤2：会员下单，锁定库存"):
            allure.attach(
                f"商品ID: {product_id}\n数量: {buy_quantity}",
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
            assert resp["data"] is not None

            created_order_sn = resp["data"]["orderSn"]
            allure.attach(created_order_sn, name="生成的订单号", attachment_type=allure.attachment_type.TEXT)
            print(f"  ✅ 下单成功: orderSn={created_order_sn}")

        with allure.step("步骤3：校验下单后库存已扣减"):
            resp = api_client.get("/debug/products")
            assert resp["code"] == 200

            current_stock = None
            for p in resp["data"]:
                if p["id"] == product_id:
                    current_stock = p["stock"]
                    break

            assert current_stock is not None
            expected_after_order = initial_stock - buy_quantity
            assert current_stock == expected_after_order, \
                f"下单后库存扣减异常: 预期 {expected_after_order}, 实际 {current_stock}"

            allure.attach(
                f"初始库存: {initial_stock}\n下单数量: {buy_quantity}\n当前库存: {current_stock}\n预期: {expected_after_order}",
                name="下单后库存校验",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 下单后库存扣减正确: {initial_stock} -> {current_stock}")

        with allure.step("步骤4：校验订单状态为待支付（status=0）"):
            resp = api_client.get(f"/oms/order/detail/{created_order_sn}")
            assert resp["code"] == 200
            assert resp["data"]["status"] == 0, f"订单状态应为 0（待支付），实际为 {resp['data']['status']}"

            allure.attach(
                f"订单号: {created_order_sn}\n状态: 0 (待支付)",
                name="订单状态校验",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 订单状态正确: 待支付 (status=0)")

        with allure.step("步骤5：Admin 端关闭订单（模拟超时未支付）"):
            allure.attach(
                f"订单号: {created_order_sn}\n关闭原因: 超时未支付（模拟）",
                name="关闭订单参数",
                attachment_type=allure.attachment_type.TEXT
            )

            resp = api_client.post("/admin/oms/order/close", json_body={
                "order_sn": created_order_sn,
                "note": "超时未支付，系统自动关闭"
            })

            assert resp["status_code"] == 200, f"关闭订单 HTTP 状态码异常: {resp['status_code']}"
            assert resp["code"] == 200, f"关闭订单业务码异常: {resp['code']}, message: {resp['message']}"
            assert resp["data"]["status"] == 4, f"关闭后订单状态应为 4（已关闭），实际为 {resp['data']['status']}"

            allure.attach(
                f"订单号: {created_order_sn}\n新状态: 4 (已关闭)",
                name="订单关闭结果",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 订单已关闭: status=4 (已关闭)")

        with allure.step("步骤6：校验订单详情状态已更新为已关闭"):
            resp = api_client.get(f"/oms/order/detail/{created_order_sn}")
            assert resp["code"] == 200
            order = resp["data"]

            assert order["status"] == 4, f"订单详情状态应为 4（已关闭），实际为 {order['status']}"
            assert order.get("close_note") == "超时未支付，系统自动关闭"
            assert order.get("close_time") is not None

            allure.attach(
                f"订单号: {order['orderSn']}\n状态: 4 (已关闭)\n关闭原因: {order.get('close_note')}\n关闭时间: {order.get('close_time')}",
                name="订单详情状态验证",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 订单详情状态验证通过: 已关闭")

        with allure.step("步骤7：核心断言 - 库存已回滚释放（白盒数据一致性校验）"):
            resp = api_client.get("/debug/products")
            assert resp["code"] == 200

            current_stock = None
            for p in resp["data"]:
                if p["id"] == product_id:
                    current_stock = p["stock"]
                    break

            assert current_stock is not None
            assert current_stock == initial_stock, \
                f"库存回滚异常: 订单关闭后库存应恢复为 {initial_stock}，实际为 {current_stock}"

            allure.attach(
                f"初始库存: {initial_stock}\n下单后: {expected_after_order}\n关闭后: {current_stock}\n回滚结果: {'✅ 已回滚' if current_stock == initial_stock else '❌ 未回滚'}",
                name="库存回滚验证（核心断言）",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 库存回滚验证通过: {expected_after_order} -> {current_stock}（恢复至初始值）")

        print("\n" + "=" * 60)
        print("🎉 订单关闭与库存回滚全链路测试通过！")
        print("=" * 60)

    finally:
        with allure.step("数据清理（Teardown）"):
            if created_order_sn:
                allure.attach(created_order_sn, name="待清理的订单号", attachment_type=allure.attachment_type.TEXT)
                print(f"\n🧹 [Teardown] 清理测试数据: 订单 {created_order_sn}")
                api_client.post("/reset")
                print(f"   (已调用 /reset 重置 Mock 数据)")


@pytest.mark.smoke
@pytest.mark.e2e
@pytest.mark.oms
@pytest.mark.dataconsistency
@allure.feature("订单模块-OMS")
@allure.story("订单全生命周期状态机")
@allure.title("订单完整生命周期流转 - 下单->支付->发货->收货")
@allure.description("测试订单完整生命周期：待支付->待发货->已发货->已完成")
@allure.severity(allure.severity_level.CRITICAL)
def test_order_full_lifecycle_e2e(api_client, member_token, admin_token):
    """订单完整生命周期状态机流转测试（链路 A 补充）

    场景：
    1. Admin 端发布新商品，初始库存 100 件
    2. Portal 端会员登录，搜索商品并加购
    3. 提交订单（待支付 status=0）
    4. Admin 端模拟支付回调（待发货 status=1）
    5. Admin 端调用发货接口（已发货 status=2）
    6. Portal 端会员确认收货（已完成 status=3）
    7. 数据断言：最终库存变为 99 件，状态机流转无误
    """
    created_order_sn = None
    product_id = None
    initial_stock = 100
    buy_quantity = 1

    try:
        with allure.step("步骤1：Admin 端发布新商品，初始库存 100 件"):
            resp = api_client.post("/admin/pms/product/create", json_body={
                "name": "测试商品-生命周期测试",
                "price": 99.00,
                "stock": initial_stock,
                "brand": "测试品牌",
                "category": "测试分类"
            })
            assert resp["code"] == 200
            product_id = resp["data"]["id"]

            allure.attach(
                f"商品ID: {product_id}\n商品名: {resp['data']['name']}\n初始库存: {initial_stock}",
                name="Admin 创建商品",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ Admin 发布商品: id={product_id}, stock={initial_stock}")

        with allure.step("步骤2：会员加购商品"):
            resp = api_client.post("/oms/cart/add", json_body={
                "product_id": product_id,
                "quantity": buy_quantity
            })
            assert resp["code"] == 200
            print(f"  ✅ 会员加购成功")

        with allure.step("步骤3：提交订单 -> 状态：待支付 (status=0)"):
            resp = api_client.post("/oms/order/generate", json_body={
                "product_id": product_id,
                "quantity": buy_quantity,
                "member_id": 1,
                "receiver_name": "李四",
                "receiver_phone": "13900139000",
                "receiver_detail_address": "上海市浦东新区xxx路xxx号"
            })
            assert resp["code"] == 200
            created_order_sn = resp["data"]["orderSn"]

            resp_detail = api_client.get(f"/oms/order/detail/{created_order_sn}")
            assert resp_detail["data"]["status"] == 0

            allure.attach(
                f"订单号: {created_order_sn}\n状态: 0 (待支付)",
                name="订单状态-待支付",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 订单已创建: status=0 (待支付)")

        with allure.step("步骤4：Admin 支付回调 -> 状态：待发货 (status=1)"):
            resp = api_client.post("/admin/oms/order/pay", json_body={
                "order_sn": created_order_sn
            })
            assert resp["code"] == 200
            assert resp["data"]["status"] == 1

            allure.attach(
                f"订单号: {created_order_sn}\n状态: 1 (待发货)\n支付时间: {time_str()}",
                name="订单状态-待发货",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 支付成功: status=1 (待发货)")

        with allure.step("步骤5：Admin 发货 -> 状态：已发货 (status=2)"):
            resp = api_client.post("/admin/oms/order/delivery", json_body={
                "order_sn": created_order_sn,
                "delivery_company": "顺丰速运",
                "delivery_sn": "SF1234567890"
            })
            assert resp["code"] == 200
            assert resp["data"]["status"] == 2

            allure.attach(
                f"订单号: {created_order_sn}\n状态: 2 (已发货)\n物流公司: 顺丰速运\n物流单号: SF1234567890",
                name="订单状态-已发货",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 发货成功: status=2 (已发货)")

        with allure.step("步骤6：会员确认收货 -> 状态：已完成 (status=3)"):
            resp = api_client.post(f"/oms/order/confirmReceive/{created_order_sn}")
            assert resp["code"] == 200
            assert resp["data"]["status"] == 3

            allure.attach(
                f"订单号: {created_order_sn}\n状态: 3 (已完成)",
                name="订单状态-已完成",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 确认收货: status=3 (已完成)")

        with allure.step("步骤7：最终校验 - 库存精准扣减 & 状态机完整流转"):
            resp = api_client.get("/debug/products")
            current_stock = None
            for p in resp["data"]:
                if p["id"] == product_id:
                    current_stock = p["stock"]
                    break

            expected_stock = initial_stock - buy_quantity
            assert current_stock == expected_stock, \
                f"最终库存异常: 预期 {expected_stock}, 实际 {current_stock}"

            resp_order = api_client.get(f"/oms/order/detail/{created_order_sn}")
            order = resp_order["data"]
            assert order["status"] == 3
            assert order["payment_time"] is not None
            assert order["delivery_time"] is not None
            assert order["receive_time"] is not None

            allure.attach(
                f"库存校验: {initial_stock} - {buy_quantity} = {current_stock} (预期 {expected_stock})\n"
                f"状态机: 0(待支付) -> 1(待发货) -> 2(已发货) -> 3(已完成) ✅ 完整流转\n"
                f"支付时间: {order['payment_time']}\n"
                f"发货时间: {order['delivery_time']}\n"
                f"收货时间: {order['receive_time']}",
                name="最终校验结果",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 最终校验通过:")
            print(f"     - 库存: {initial_stock} -> {current_stock}")
            print(f"     - 状态机: 0 -> 1 -> 2 -> 3 完整流转")

        print("\n" + "=" * 60)
        print("🎉 订单完整生命周期 E2E 测试通过！")
        print("=" * 60)

    finally:
        with allure.step("数据清理（Teardown）"):
            if created_order_sn:
                print(f"\n🧹 [Teardown] 清理测试数据")
                api_client.post("/reset")
                print(f"   (已调用 /reset 重置 Mock 数据)")


def time_str():
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")
