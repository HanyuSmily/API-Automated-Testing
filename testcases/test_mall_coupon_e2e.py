import pytest
import allure
import uuid


@pytest.mark.smoke
@pytest.mark.e2e
@pytest.mark.sms
@pytest.mark.coupon
@pytest.mark.oms
@pytest.mark.dataconsistency
@allure.feature("营销模块-SMS")
@allure.story("优惠券领券核销全链路")
@allure.title("优惠券领取-下单核销-状态校验全流程 E2E 测试")
@allure.description("测试链路：Admin创建优惠券 -> 会员领取 -> 加购 -> 使用优惠券下单 -> 校验应付金额 -> 校验优惠券已使用状态")
@allure.severity(allure.severity_level.CRITICAL)
def test_coupon_redeem_e2e(api_client, member_token, admin_token):
    """优惠券领券核销全链路 E2E 测试（链路 B）

    场景：
    1. Admin 端创建一张"满100减20"的优惠券，限定发放 10 张
    2. Portal 端会员登录，调用领券接口
    3. Portal 端将会员加购价值超过 100 元的商品
    4. 提交订单，传入优惠券 ID 进行核销
    5. 数据断言：
       - 订单应付金额（payAmount）= 商品总价 - 20 元
       - "我的优惠券"接口中，该券状态变为"已使用"（status=1）
    """
    created_coupon_id = None
    created_order_sn = None
    initial_stock = None
    product_id = None

    try:
        with allure.step("步骤1：Admin 端创建满减优惠券"):
            coupon_name = f"满100减20-测试券-{uuid.uuid4().hex[:6]}"
            coupon_data = {
                "name": coupon_name,
                "amount": 20.00,
                "min_point": 100.00,
                "publish_count": 10,
                "per_limit": 1,
                "type": 0,
                "platform": 0
            }
            allure.attach(
                f"券名: {coupon_name}\n满减: 满{coupon_data['min_point']}减{coupon_data['amount']}\n发放数量: {coupon_data['publish_count']}\n每人限领: {coupon_data['per_limit']}",
                name="优惠券创建参数",
                attachment_type=allure.attachment_type.TEXT
            )

            resp = api_client.post("/admin/sms/coupon/create", json_body=coupon_data)

            assert resp["status_code"] == 200, f"创建优惠券 HTTP 状态码异常: {resp['status_code']}"
            assert resp["code"] == 200, f"创建优惠券业务码异常: {resp['code']}, message: {resp['message']}"
            assert resp["data"] is not None

            created_coupon_id = resp["data"]["id"]
            allure.attach(str(created_coupon_id), name="创建的优惠券ID", attachment_type=allure.attachment_type.TEXT)
            print(f"  ✅ 已创建优惠券: id={created_coupon_id}, name={coupon_name}")

        with allure.step("步骤2：会员领取优惠券"):
            allure.attach(str(created_coupon_id), name="领取的优惠券ID", attachment_type=allure.attachment_type.TEXT)

            resp = api_client.post("/sms/coupon/receive", json_body={"coupon_id": created_coupon_id})

            assert resp["status_code"] == 200, f"领取优惠券 HTTP 状态码异常: {resp['status_code']}"
            assert resp["code"] == 200, f"领取优惠券业务码异常: {resp['code']}, message: {resp['message']}"
            assert resp["data"] is not None
            assert resp["data"]["status"] == 0, "优惠券领取后状态应为 0（未使用）"
            assert resp["data"]["coupon_id"] == created_coupon_id

            allure.attach(
                f"会员券ID: {resp['data']['id']}\n状态: {resp['data']['status']} (0=未使用)",
                name="领取结果",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 会员领取优惠券成功: coupon_id={created_coupon_id}")

        with allure.step("步骤3：查询商品列表并选择符合满减门槛的商品"):
            resp = api_client.get("/pms/product/list", params={"pageNum": 1, "pageSize": 10})
            assert resp["status_code"] == 200
            assert resp["code"] == 200

            products = resp["data"]["list"]
            target_product = None
            for p in products:
                if p["price"] >= 100:
                    target_product = p
                    break

            assert target_product is not None, "未找到价格>=100元的测试商品"
            product_id = target_product["id"]
            product_price = target_product["price"]
            initial_stock = target_product["stock"]
            buy_quantity = 1

            allure.attach(
                f"商品ID: {product_id}\n商品名: {target_product['name']}\n单价: {product_price}\n数量: {buy_quantity}\n初始库存: {initial_stock}",
                name="选购商品信息",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 选择商品: {target_product['name']}, 单价={product_price}, 库存={initial_stock}")

        with allure.step("步骤4：添加商品到购物车"):
            resp = api_client.post("/oms/cart/add", json_body={
                "product_id": product_id,
                "quantity": buy_quantity
            })
            assert resp["status_code"] == 200
            assert resp["code"] == 200
            print(f"  ✅ 已添加到购物车")

        with allure.step("步骤5：使用优惠券提交订单（核销）"):
            total_amount = product_price * buy_quantity
            expected_pay_amount = total_amount - 20.00

            allure.attach(
                f"商品总价: {total_amount}\n优惠券抵扣: 20.00\n预期应付: {expected_pay_amount}",
                name="金额计算预期",
                attachment_type=allure.attachment_type.TEXT
            )

            resp = api_client.post("/oms/order/generate", json_body={
                "product_id": product_id,
                "quantity": buy_quantity,
                "member_id": 1,
                "coupon_id": created_coupon_id,
                "receiver_name": "张三",
                "receiver_phone": "13800138000",
                "receiver_detail_address": "北京市朝阳区xxx街道xxx号"
            })

            assert resp["status_code"] == 200, f"下单 HTTP 状态码异常: {resp['status_code']}"
            assert resp["code"] == 200, f"下单业务码异常: {resp['code']}, message: {resp['message']}"
            assert resp["data"] is not None

            created_order_sn = resp["data"]["orderSn"]
            actual_pay_amount = resp["data"]["pay_amount"]
            discount_amount = resp["data"].get("discount_amount", 0)

            allure.attach(created_order_sn, name="生成的订单号", attachment_type=allure.attachment_type.TEXT)
            allure.attach(str(actual_pay_amount), name="实际应付金额", attachment_type=allure.attachment_type.TEXT)

            assert abs(actual_pay_amount - expected_pay_amount) < 0.01, \
                f"应付金额计算错误: 预期 {expected_pay_amount}, 实际 {actual_pay_amount}"
            assert discount_amount == 20.00, f"优惠券抵扣金额错误: 预期 20.00, 实际 {discount_amount}"

            print(f"  ✅ 下单成功: orderSn={created_order_sn}")
            print(f"     商品总价: {total_amount}")
            print(f"     优惠券抵扣: {discount_amount}")
            print(f"     应付金额: {actual_pay_amount}")

        with allure.step("步骤6：校验优惠券状态 - 已使用（数据闭环断言）"):
            resp = api_client.get("/sms/coupon/mine", params={"status": 1})

            assert resp["status_code"] == 200
            assert resp["code"] == 200

            used_coupons = resp["data"]["list"]
            found = False
            for mc in used_coupons:
                if mc["coupon_id"] == created_coupon_id:
                    found = True
                    assert mc["status"] == 1, f"优惠券状态应为 1（已使用），实际为 {mc['status']}"
                    assert mc["use_order_sn"] == created_order_sn, "优惠券使用的订单号不匹配"
                    break

            assert found, "在已使用优惠券列表中未找到该券"

            allure.attach(
                f"优惠券ID: {created_coupon_id}\n状态: 1 (已使用)\n关联订单: {created_order_sn}",
                name="优惠券状态验证结果",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 优惠券状态验证通过: 已标记为已使用，关联订单 {created_order_sn}")

        with allure.step("步骤7：库存扣减校验（白盒数据断言）"):
            resp = api_client.get("/debug/products")
            assert resp["code"] == 200

            current_product = None
            for p in resp["data"]:
                if p["id"] == product_id:
                    current_product = p
                    break

            assert current_product is not None
            expected_stock = initial_stock - buy_quantity
            assert current_product["stock"] == expected_stock, \
                f"库存扣减不一致: 预期 {expected_stock}, 实际 {current_product['stock']}"

            allure.attach(
                f"初始库存: {initial_stock}\n扣减数量: {buy_quantity}\n当前库存: {current_product['stock']}\n预期库存: {expected_stock}",
                name="库存校验结果",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 库存扣减校验通过: {initial_stock} - {buy_quantity} = {current_product['stock']}")

        print("\n" + "=" * 60)
        print("🎉 优惠券领券核销全链路测试通过！")
        print("=" * 60)

    finally:
        with allure.step("数据清理（Teardown）"):
            cleanup_info = []
            if created_order_sn:
                cleanup_info.append(f"订单: {created_order_sn}")
            if created_coupon_id:
                cleanup_info.append(f"优惠券: {created_coupon_id}")

            allure.attach(
                "\n".join(cleanup_info),
                name="待清理数据",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"\n🧹 [Teardown] 清理测试数据: {', '.join(cleanup_info) if cleanup_info else '无'}")
            api_client.post("/reset")
            print(f"   (已调用 /reset 重置 Mock 数据)")


@pytest.mark.exception
@pytest.mark.sms
@pytest.mark.coupon
@pytest.mark.api
@allure.feature("营销模块-SMS")
@allure.story("优惠券异常场景")
@allure.title("重复领取优惠券 - 超出限领次数")
@allure.severity(allure.severity_level.NORMAL)
def test_coupon_repeat_receive(api_client, member_token, admin_token):
    """重复领券异常场景 - 超出每人限领次数"""
    created_coupon_id = None

    try:
        with allure.step("准备：创建每人限领1张的优惠券"):
            resp = api_client.post("/admin/sms/coupon/create", json_body={
                "name": f"限领1张测试券-{uuid.uuid4().hex[:6]}",
                "amount": 10.00,
                "min_point": 50.00,
                "publish_count": 100,
                "per_limit": 1
            })
            assert resp["code"] == 200
            created_coupon_id = resp["data"]["id"]

        with allure.step("第一次领取 - 成功"):
            resp = api_client.post("/sms/coupon/receive", json_body={"coupon_id": created_coupon_id})
            assert resp["code"] == 200
            assert resp["data"]["status"] == 0
            print(f"  ✅ 第一次领取成功")

        with allure.step("第二次领取 - 应失败（超出限领次数）"):
            resp = api_client.post("/sms/coupon/receive", json_body={"coupon_id": created_coupon_id})

            assert resp["status_code"] == 200
            assert resp["code"] == 400
            assert "限领" in resp["message"] or "已领取" in resp["message"]

            allure.attach(
                f"业务码: {resp['code']}\n消息: {resp['message']}",
                name="重复领券异常验证",
                attachment_type=allure.attachment_type.TEXT
            )
            print(f"  ✅ 重复领券被正确拒绝: {resp['message']}")

    finally:
        api_client.post("/reset")
