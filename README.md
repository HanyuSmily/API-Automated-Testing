# 这是一个基于 HTTPRunner 架构的API自动化测试框架

- 作者：Smily
- 我参考了架构的设计并根据自己测试需求设计一个API测试框架，本设计做了大篇幅改动
- 目标测试对象：开源电商系统 **mall**（mall-portal 前台 + mall-admin 后台）

## 项目架构图

![alt text](image.png)

---

## 核心功能一览

| 功能模块 | 说明 | 核心文件 |
|---------|------|---------|
| 核心引擎 | 请求发送、变量解析、断言校验、结果聚合 | `core/runner.py` `core/step.py` `core/client.py` `core/parser.py` |
| 数据驱动 | 读取 CSV/JSON/Excel 文件循环执行同一用例 | `utils/data_loader.py` `data/parms.py` |
| 全局 Hook | debugtalk.py 中自定义函数，用例中 `${func()}` 调用 | `debugtalk.py` `core/loader.py` |
| 断言升级 | 14 种断言：eq/ne/contains/type/regex/**json_schema** 等 | `utils/assert_utils.py` |
| 环境管理 | Dev/QA/Prod/Mock 一键切换，自动注入 base_url | `env.yml` `core/env_manager.py` |
| 失败重试 | Step 级重试（网络异常/断言失败）+ pytest 级重试 | `core/step.py` `pytest-rerunfailures` |
| 可视化报告 | pytest-html 单文件报告 + Allure + 失败日志捕获 | `conftest.py` `pytest.ini` |
| **Mock 服务器** | **FastAPI 轻量级 mall 电商 Mock，内存状态保持，支持全链路数据闭环断言** | `mock_mall_server.py` |
| **业务测试用例** | **mall 电商 3 条核心 E2E 链路 + 异常场景 + 白盒数据一致性校验** | `testcases/` |
| **用例分类管理** | **pytest.mark 标签体系：smoke/exception/oms/sms/coupon 等 17 种标签** | `pytest.ini` |
| **可视化前端** | **Streamlit 极简 Web 界面：环境切换、一键运行、Allure 报告内嵌** | `app.py` |
| CI/CD | GitLab MR 自动触发、Docker 镜像打包 | `.gitlab-ci.yml` `Dockerfile` |

---

## 业务测试覆盖（mall 电商系统）

### 三大核心 E2E 链路

| 链路 | 说明 | 测试文件 |
|------|------|---------|
| **链路 A：订单全生命周期** | Admin 建商品 → 会员加购 → 下单(待支付) → 支付回调(待发货) → 发货(已发货) → 确认收货(已完成) → 库存扣减白盒校验 | `test_mall_refund_e2e.py::test_order_full_lifecycle_e2e` |
| **链路 B：优惠券领券核销** | Admin 建满减券 → 会员领券 → 加购达标商品 → 使用优惠券下单 → 应付金额=总价-抵扣额 → 券状态变"已使用" | `test_mall_coupon_e2e.py::test_coupon_redeem_e2e` |
| **链路 C：订单关闭与库存回滚** | 会员下单锁定库存 → Admin 关闭订单(超时未支付) → 状态变 4(已关闭) → 库存自动回滚释放 | `test_mall_refund_e2e.py::test_order_close_stock_rollback_e2e` |

### 异常/边界场景

| 模块 | 场景 | 测试文件 |
|------|------|---------|
| 登录 | 账号不存在、密码错误、连续 5 次失败账户锁定 | Mock 服务器支持 |
| 商品列表 | pageSize=0 容错、非法参数返回 400、大页数截断 | Mock 服务器支持 |
| 购物车 | 已下架商品、库存为 0、超单品上限 99 件 | Mock 服务器支持 |
| 下单 | 幂等性防重复提交、金额一致性校验、优惠券门槛校验 | Mock 服务器支持 |
| 优惠券 | 重复领券(超每人限领)、已过期、已领完 | `test_mall_coupon_e2e.py::test_coupon_repeat_receive` |
| 订单 | 查询不存在的订单 | `test_mall_order_e2e.py::test_order_not_found` |

### Mock 服务器核心接口清单

**Admin 端**：商品发布、支付回调、订单发货、订单关闭、优惠券创建
**Portal 端**：会员登录、商品列表/详情、购物车增/查、订单生成/查询/确认收货、优惠券领/查

> 所有接口遵循 mall 项目统一响应格式 `{code, message, data}`，内存数据状态保持，支持数据闭环断言。

---

## 用例分类标签体系（pytest.mark）

所有测试用例均已标注分类标签，支持灵活筛选运行。

### 标签分类

| 维度 | 标签 | 说明 |
|------|------|------|
| 测试类型 | `smoke` | 冒烟测试 - 核心主链路，每次提交必跑（4 个用例） |
| | `regression` | 回归测试 - 全量用例集 |
| | `e2e` | 端到端全链路测试 |
| | `exception` | 异常/边界场景测试 |
| 业务模块 | `ums` | UMS 会员模块 |
| | `pms` | PMS 商品模块 |
| | `oms` | OMS 订单模块 |
| | `sms` | SMS 营销模块 |
| 专项 | `coupon` | 优惠券相关 |
| | `refund` | 退款/逆向流程 |
| | `idempotent` | 幂等性测试 |
| | `dataconsistency` | 数据一致性/白盒校验 |

### 常用运行命令

```bash
# 只跑冒烟用例（4个核心链路）
pytest -m smoke

# 只跑异常场景用例
pytest -m exception

# 跑 OMS 订单模块所有用例
pytest -m oms

# 跑 SMS 营销模块 + 优惠券
pytest -m "sms and coupon"

# 跑所有 E2E 链路（不含异常单接口）
pytest -m "e2e and not exception"
```

---

## 项目目录结构

```
API-Automated-Testing/
├── core/                           # 核心框架代码
│   ├── __init__.py
│   ├── client.py                   # HTTP 会话封装（基于 requests，自动记录日志与耗时）
│   ├── env_manager.py              # 环境管理器（Dev/QA/Prod 一键切换，加载 env.yml）
│   ├── loader.py                   # debugtalk.py 加载器（动态导入自定义函数）
│   ├── parser.py                   # 变量/函数解析器（解析 $var、${func()} 语法）
│   ├── runner.py                   # 测试会话运行器（调度步骤执行、聚合结果）
│   └── step.py                     # 测试步骤（请求+断言+失败重试编排）
│
├── api/                            # API 客户端层
│   ├── __init__.py
│   └── base_api.py                 # 统一 API 客户端（会话复用、Allure 失败留证）
│
├── testcases/                      # mall 电商业务测试用例
│   ├── __init__.py
│   ├── conftest.py                 # 业务层 fixtures（api_client / member_token / admin_token）
│   ├── test_mall_order_e2e.py      # 订单主链路 E2E + 商品分页 + 异常查询
│   ├── test_mall_coupon_e2e.py     # 链路 B：优惠券领券核销全链路 + 重复领券异常
│   └── test_mall_refund_e2e.py     # 链路 C：订单关闭库存回滚 + 链路 A：订单全生命周期
│
├── data/                           # 数据文件目录
│   ├── __init__.py
│   ├── parms.py                    # DDT 入口（加载外部数据文件并参数化）
│   ├── test_users.csv              # 示例数据（CSV 格式）
│   ├── test_users.json             # 示例数据（JSON 格式）
│   ├── test_users.xlsx             # 示例数据（Excel 格式）
│   └── test_cases/
│       ├── __init__.py
│       └── demo_test.yml           # YAML 测试用例示例
│
├── logs/                           # 日志模块
│   ├── __init__.py
│   └── runner.py                   # 日志运行器
│
├── utils/                          # 工具模块
│   ├── __init__.py
│   ├── assert_utils.py             # 断言工具（eq/contains/type/regex/json_schema 等 14 种）
│   ├── data_loader.py              # 数据加载器（解析 CSV/JSON/Excel 为参数化数据）
│   └── logger.py                   # 日志配置
│
├── reports/                        # 报告输出目录（自动生成）
│   ├── report.html                 # pytest-html 单文件报告
│   └── allure_data/                # Allure 原始数据
│
├── .github/
│   └── workflows/
│       └── main.yml                # GitHub Actions CI 配置
│
├── .gitlab-ci.yml                  # GitLab CI/CD 配置（MR 触发自动测试）
├── .dockerignore                   # Docker 构建忽略文件
├── app.py                          # Streamlit 可视化前端（环境切换 + 一键运行 + 报告内嵌）
├── conftest.py                     # pytest 全局夹具（venv 检查、日志捕获、报告增强）
├── debugtalk.py                    # 全局 Hook（自定义函数：get_token/sign/gen_timestamp 等）
├── Dockerfile                      # Docker 镜像构建文件
├── env.yml                         # 环境配置（Mock/Dev/QA/Prod 的 base_url 与数据库连接）
├── main.py                         # 程序入口
├── mock_mall_server.py             # FastAPI Mock 服务器（mall 电商系统，内存状态保持）
├── pytest.ini                      # pytest 配置（报告生成、标记注册、警告过滤）
├── README.md                       # 项目说明文档
├── requirements.txt                # Python 依赖清单
├── run_tests.py                    # 一键运行脚本（支持 --env/--allure/--open）
├── test_assert.py                  # 断言能力测试
├── test_debugtalk.py               # 全局 Hook 测试
├── test_env.py                     # 环境管理测试
├── test_main.py                    # 主流程测试
├── test_params.py                  # 数据驱动测试
├── test_report.py                  # 报告生成测试
├── test_retry.py                   # 重试机制测试
└── TRD.md                          # 测试需求文档（全链路业务场景设计）
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

额外安装（运行 Mock 服务器 + 可视化前端）：

```bash
pip install fastapi uvicorn streamlit allure-pytest
```

### 2. 启动 Mock 服务器（本地测试用）

```bash
python mock_mall_server.py
# 访问 http://127.0.0.1:8080/health 验证
```

### 3. 运行业务测试

```bash
# 全量测试
pytest testcases/ -v

# 只跑冒烟用例
pytest testcases/ -v -m smoke

# 只跑异常场景
pytest testcases/ -v -m exception
```

### 4. 启动可视化前端

```bash
streamlit run app.py
# 访问 http://localhost:8501
```

### 5. 生成 Allure 报告

```bash
# 运行测试并生成原始数据
pytest testcases/ --alluredir=reports/allure_data

# 使用 Allure CLI 渲染 HTML 报告
allure generate reports/allure_data -o reports/allure_html --clean

# 或直接打开预览
allure serve reports/allure_data
```

---

## 环境准备

### Python 版本

本项目基于 Python 3.10 开发，推荐使用项目自带的虚拟环境：

```bash
# Windows
f:\XU\API-Automated-Testing\.venv\Scripts\python.exe -m pytest

# Linux / Mac
source .venv/bin/activate && pytest
```

### 环境切换

```bash
# 通过环境变量切换（CI/CD 友好）
# Windows PowerShell
$env:TEST_ENV="qa"; pytest

# Linux / Mac
TEST_ENV=prod pytest
```

```python
# 代码中运行时切换
from core.env_manager import get_env_manager
get_env_manager().switch_env("prod")

# 读取数据库配置
db = get_env_manager().db_config
```

---

## 框架核心能力使用说明

### 1. 数据驱动测试

将数据从外部文件（CSV/JSON/Excel）加载到测试用例中，使用 pytest.mark.parametrize 装饰器参数化：

```python
from data.parms import load_params

data = load_params("test_users.csv", converters={"user_id": int})

@pytest.mark.parametrize("params", data)
def test_xxx(params):
    runner = SessionRunner()
    runner.session_variables = {"user_id": params["user_id"]}
```

### 2. debugtalk.py 全局 Hook

在 `debugtalk.py` 定义自定义函数，用例中通过 `${func()}` 调用：

```python
# debugtalk.py
def get_token():
    return f"token_{uuid.uuid4().hex}"

# 用例中
step = Step(
    name="带签名的请求",
    request={
        "url": "/api?token=${get_token()}&ts=${gen_timestamp()}",
        "method": "GET"
    },
)
```

### 3. JSON Schema 断言

```python
step = Step(
    name="接口合规性校验",
    request={"url": "/user", "method": "GET"},
    validate=[
        {"check": "status_code", "assert_type": "eq", "expect": 200},
        {"check": "body", "assert_type": "json_schema", "expect": {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "email": {"type": "string", "format": "email"},
            },
        }},
    ],
)
```

### 4. 失败重试机制

**Step 级重试**（单个接口）：

```python
step = Step(
    name="偶发不稳定接口",
    request={"url": "/flaky", "method": "GET"},
    validate=[{"check": "status_code", "assert_type": "eq", "expect": 200}],
    retry_times=3,
    retry_interval=2,
)
```

**pytest 级重试**（整个用例）：

```python
@pytest.mark.flaky(reruns=2, reruns_delay=1)
def test_unstable_api():
    ...
```

---

## CI/CD 自动触发

**GitLab MR 流程**：提交 Merge Request 后自动触发 `syntax-check` + `run-tests`，在 MR 界面直接查看测试结果与报告下载。

**Docker 运行**：

```bash
docker build -t api-auto-test .
docker run --rm -e TEST_ENV=qa api-auto-test
docker run --rm -v $(pwd)/reports:/app/reports api-auto-test
```
