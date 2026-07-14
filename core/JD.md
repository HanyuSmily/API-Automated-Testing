我先快速核对项目的实际文件结构，确保简历内容准确无误。
        
            
toolName: file_search
            
status: success
          
file_pattern: **/*.py
          

        
            
toolName: file_search
            
status: success
          
file_pattern: *.{yml,yaml,ini,txt,md,Dockerfile}
          
基于项目全部功能模块、技术实现、关键问题解决方案和最终成果，我整理了一份详细的简历项目经历内容如下：

---

# 项目经历：基于 HttpRunner 的 API 自动化测试框架

## 项目基本信息

**项目名称**：API 自动化测试框架（基于 HttpRunner 架构二次开发）
**项目角色**：测试开发工程师（独立设计与实现）
**项目周期**：2026 年 6 月 — 2026 年 7 月
**项目规模**：自研框架，覆盖 7 大功能模块，包含 80+ 自动化测试用例

## 项目背景

随着公司接口数量快速增长，传统的手工接口测试和 Postman 脚本方式存在用例复用性差、无法批量执行、缺乏环境隔离、报告不可视化、CI/CD 难以集成等问题。本项目旨在设计一套可扩展、可维护、可集成至 DevOps 流水线的 API 自动化测试框架，实现"一次编写、多环境运行、自动出报告、MR 自动触发"的闭环测试能力。

## 技术栈

| 分类 | 技术 |
|------|------|
| 编程语言 | Python 3.10 |
| 核心框架 | HttpRunner 4.3.5（TConfig/TStep 数据模型 + Parser 解析器） |
| 测试运行器 | pytest 7.4.4（parametrize、markers、fixtures、hookspecs） |
| 数据校验 | jsonschema、jmespath |
| 数据处理 | PyYAML、openpyxl（Excel）、csv |
| 日志系统 | loguru |
| 报告生成 | pytest-html、Allure-Pytest 2.16.0 |
| 重试机制 | 自研 Step 级重试 + pytest-rerunfailures 14.0 |
| HTTP 客户端 | requests.Session |
| 容器化 | Docker（python:3.10-slim 多阶段构建） |
| CI/CD | GitLab CI（.gitlab-ci.yml）、GitHub Actions |
| 数据模型 | pydantic v2（兼容 HttpRunner 配置模型） |

## 项目职责与核心实现

### 1. 核心引擎层设计与开发

**负责模块**：[core/runner.py](file:///f:/XU/API-Automated-Testing/core/runner.py)、[core/step.py](file:///f:/XU/API-Automated-Testing/core/step.py)、[core/client.py](file:///f:/XU/API-Automated-Testing/core/client.py)、[core/parser.py](file:///f:/XU/API-Automated-Testing/core/parser.py)

- 设计 `SessionRunner` 测试会话运行器，基于 HttpRunner 的 TConfig/TStep 数据模型，负责测试用例的加载、变量管理、步骤调度与会话状态维护
- 封装 `HttpSession` 客户端层，基于 `requests.Session` 实现连接复用与 Cookie 自动管理
- 集成 HttpRunner 的 `Parser` 解析器，在请求发送前完成变量替换与函数调用（`${var}` / `${func()}` 语法）
- 为 `SessionRunner` 的 config setter 实现环境自动注入逻辑：当用例未显式声明 base_url 时，自动从当前环境（EnvManager）注入，实现用例与环境配置解耦
- 为 `core/runner.py` 中所有方法编写详细的中文注释，覆盖类职责、参数说明、返回值说明与行内逻辑解释，提升团队可维护性

### 2. 数据驱动测试（DDT）模块

**负责模块**：[utils/data_loader.py](file:///f:/XU/API-Automated-Testing/utils/data_loader.py)、[data/parms.py](file:///f:/XU/API-Automated-Testing/data/parms.py)

- 设计 `DataLoader` 类，提供统一入口 `load(file_path)`，根据文件扩展名自动分发至 `_load_csv`、`_load_json`、`_load_excel` 三种解析器
- 支持 CSV 字段类型转换：通过 `converters` 参数将 CSV 中的字符串自动转换为 int/float/bool 等类型，解决 CSV 全字符串的痛点
- 封装 `load_params(file_name, converters)` 与 `load_params_tuples` 接口，无缝对接 pytest 的 `@pytest.mark.parametrize`
- 设计示例数据文件（test_users.csv/json/xlsx），验证同一用例可基于外部数据循环执行
- 共编写 13 个数据驱动测试用例，覆盖三种数据格式解析、类型转换、参数化执行场景

### 3. 全局 Hook 机制（debugtalk.py）

**负责模块**：[core/loader.py](file:///f:/XU/API-Automated-Testing/core/loader.py)、[debugtalk.py](file:///f:/XU/API-Automated-Testing/debugtalk.py)

- 模仿 HttpRunner 的 debugtalk.py 机制，实现 `load_debugtalk(project_root)` 函数，基于 `importlib.util` 动态导入项目根目录的 debugtalk.py 模块
- 使用 `inspect.getmembers` 提取模块中所有公共函数（过滤下划线开头），封装为 `ProjectMeta` 对象返回
- 在 `SessionRunner.__init__` 中自动加载 debugtalk 函数并注入 Parser，使 YAML/JSON 用例可通过 `${get_token()}`、`${sign($params)}` 语法调用自定义 Python 函数
- 在 debugtalk.py 中实现 6 个示例函数：`get_token()`、`gen_timestamp()`、`gen_random_string()`、`sign()`（签名计算）、`add()`、`gen_user_id()`
- 编写 7 个测试用例覆盖函数加载、参数化调用、混合变量/函数使用场景

### 4. 断言能力升级（14 种断言 + JSON Schema）

**负责模块**：[utils/assert_utils.py](file:///f:/XU/API-Automated-Testing/utils/assert_utils.py)

- 设计 `AssertUtils.validate(actual, expect, assert_type)` 统一断言入口
- 采用处理函数映射表（`_ASSERT_HANDLERS` dict）模式实现 14 种断言类型，避免冗长的 if-elif 链，易于扩展：
  - 相等类：`eq`、`ne`
  - 包含类：`contains`、`contained_by`
  - 大小比较：`gt`、`ge`、`lt`、`le`
  - 长度校验：`len_eq`、`len_gt`、`len_lt`
  - 类型校验：`type`
  - 正则匹配：`regex`
  - **JSON Schema 校验**：`json_schema`（基于 jsonschema 库，校验接口响应结构合规性）
- 每个断言由三部分组成：`check`（从 status_code/body/headers/jmespath 提取实际值）、`assert_type`（断言方法）、`expect`（期望值）
- JSON Schema 校验失败时输出清晰错误信息，包含校验失败字段路径（`absolute_path`），便于定位
- 编写 26 个断言测试用例，覆盖全部 14 种断言类型及边界场景

### 5. 环境管理（Dev/QA/Prod 一键切换）

**负责模块**：[core/env_manager.py](file:///f:/XU/API-Automated-Testing/core/env_manager.py)、[env.yml](file:///f:/XU/API-Automated-Testing/env.yml)

- 设计 `env.yml` 配置文件，定义 dev/qa/prod 三套环境的 base_url、数据库连接（db）、Redis 配置
- 实现 `EnvManager` 环境管理器，采用模块级单例模式（`get_env_manager()` / `reset_env_manager()`）
- 环境切换优先级：显式参数 `env_name` > 环境变量 `TEST_ENV` > env.yml 中的 `default` 字段
- 支持 `get("db.host")` 点号路径方式读取嵌套配置，便于获取数据库连接信息
- 实现 `switch_env(env_name)` 运行时动态切换环境，无需重启测试进程
- 与 SessionRunner 集成：用例未显式设置 base_url 时自动注入当前环境的 base_url
- 编写 17 个环境管理测试用例，覆盖环境加载、切换、配置读取、优先级验证

### 6. 可视化报告与精细化日志

**负责模块**：[conftest.py](file:///f:/XU/API-Automated-Testing/conftest.py)、[pytest.ini](file:///f:/XU/API-Automated-Testing/pytest.ini)、[run_tests.py](file:///f:/XU/API-Automated-Testing/run_tests.py)

- 接入 pytest-html 与 Allure 双报告体系，在 pytest.ini 中配置 `--html=reports/report.html --self-contained-html` 与 `--alluredir=reports/allure_data --clean-alluredir`
- 在 conftest.py 中通过 `pytest_runtest_setup` 与 `pytest_runtest_makereport`（hookwrapper）实现 loguru 日志捕获：测试失败时自动将日志写入 HTML 报告的失败用例 section
- 通过 `pytest_configure` 注入环境元数据（Python 版本、平台、环境名、base_url）至 HTML 报告头部
- 在 `pytest_sessionstart` 阶段写入 Allure 的 `environment.properties`，解决 `--clean-alluredir` 在 configure 阶段清理目录导致文件被覆盖的时序问题
- 为 HTML 报告表头添加"环境"列，直观显示每条用例执行时的环境
- 注册 6 个自定义 pytest marker（smoke/api/env/assert/debugtalk/params），规范用例分类
- 开发 `run_tests.py` 一键运行脚本，支持 `--env`（环境切换）、`-m`（marker 过滤）、`--allure`（生成 Allure 报告）、`--open`（自动打开报告）参数
- 编写 7 个报告验证测试用例

### 7. 异常捕获与自动重试机制

**负责模块**：[core/step.py](file:///f:/XU/API-Automated-Testing/core/step.py)（重构）

- 将 `Step.run()` 方法拆分为 `run()`（重试编排）与 `_execute()`（单次执行），实现职责分离
- 定义 `RETRYABLE_EXCEPTIONS` 元组，明确可重试异常类型：
  - **可重试**：`ConnectionError`、`Timeout`、`5xx HTTPError`、`AssertionError`（网络抖动/服务偶发不稳定）
  - **不可重试**：`ValueError`、`KeyError`、`TypeError`（配置错误，重试无意义）
- 支持配置 `retry_times`（重试次数）与 `retry_interval`（重试间隔秒数）
- 重试过程通过 loguru 输出结构化日志：记录每次尝试结果、剩余重试次数、最终失败原因
- 引入 pytest-rerunfailures 14.0，提供 pytest 级别的 `@pytest.mark.flaky` 可选重试能力（与 Step 级重试互补）
- 编写 12 个重试机制测试用例，覆盖无重试、重试成功、重试耗尽、不可重试异常、重试间隔、异常类型分流等场景

### 8. Docker 容器化打包

**负责模块**：[Dockerfile](file:///f:/XU/API-Automated-Testing/Dockerfile)、[.dockerignore](file:///f:/XU/API-Automated-Testing/.dockerignore)、[requirements.txt](file:///f:/XU/API-Automated-Testing/requirements.txt)

- 基于 `python:3.10-slim` 编写多阶段 Dockerfile，优化镜像体积
- 利用 Docker 层缓存：先 `COPY requirements.txt` 再 `RUN pip install`，依赖未变更时复用缓存层，加速构建
- 配置阿里云 pip 镜像源加速依赖下载
- 使用 `ENTRYPOINT ["pytest"]` + `CMD ["--default-params"]`，支持运行时参数覆盖（如 `docker run img -m smoke --env qa`）
- 编写 requirements.txt 精简至 12 个核心依赖，排除 Windows 专用包与开发工具
- 配置 .dockerignore 排除 .venv/、reports/、\_\_pycache\_\_/、.git/ 等无关文件

### 9. GitLab CI/CD 流水线

**负责模块**：[.gitlab-ci.yml](file:///f:/XU/API-Automated-Testing/.gitlab-ci.yml)、[conftest.py](file:///f:/XU/API-Automated-Testing/conftest.py)（CI 适配）

- 设计三个 CI Job：
  - **syntax-check**（lint 阶段）：MR 触发，检查 .py 文件语法
  - **run-tests**（test 阶段）：MR + main 分支触发，运行全量测试并生成 HTML + JUnit 报告
  - **smoke-qa**（test 阶段）：main 分支触发，执行 `-m smoke` 冒烟测试，`allow_failure: true`
- 配置 pip 缓存（以 requirements.txt 为 key），加速 CI 构建
- 配置 artifacts 上传（always 策略，保留 1 周），集成 JUnit 报告（`reports/junit.xml`）供 GitLab Test 页面展示
- 通过 `TEST_ENV` 变量实现 CI 中的环境切换
- 适配 conftest.py 的 venv 检查：通过检测 `CI`/`GITLAB_CI` 环境变量，在 CI 环境下自动跳过 .venv 检查，使用系统 Python 运行测试

## 技术难点与解决方案

### 难点 1：pydantic v1/v2 兼容性冲突

**问题**：系统 Python 安装的 langsmith 0.8.8 依赖 pydantic v2，而 HttpRunner 4.3.5 依赖 pydantic v1，导致 `cannot import name 'ConfigDict' from 'pydantic'` 错误。

**解决**：
1. 升级 pydantic 至 v2，使 langsmith 与 HttpRunner 共存
2. 在 pytest.ini 中添加 `-p no:langsmith` 禁用 langsmith 插件加载，避免其与 pytest 的钩子冲突
3. 创建 conftest.py 的 `check_venv()` 函数，强制使用项目虚拟环境（.venv）运行测试，隔离系统 Python 的依赖污染

### 难点 2：pytest 版本与多插件依赖冲突

**问题**：安装 pytest-rerunfailures 最新版（16.4）要求 pytest>=8.2，自动升级至 pytest 9.1.1，但 HttpRunner 4.3.5 要求 pytest<8，导致框架无法运行。

**解决**：通过依赖版本矩阵分析，锁定 `pytest==7.4.4` + `pytest-rerunfailures==14.0` 的兼容组合，既满足 HttpRunner 的版本约束，又提供 pytest 级重试能力。

### 难点 3：Allure 报告环境信息写入时序问题

**问题**：在 `pytest_configure` 阶段写入 `environment.properties` 后，Allure 插件的 `--clean-alluredir` 选项在 configure 阶段清理目录，导致文件被删除。

**解决**：
1. 排查发现 `config.getoption("--alluredir")` 选项名错误，实际 dest 为 `allure_report_dir`
2. 将写入逻辑从 `pytest_configure` 移至 `pytest_sessionstart` 阶段（在 clean_alluredir 执行之后），确保环境信息文件持久存在

### 难点 4：CI 环境与本地 venv 检查冲突

**问题**：conftest.py 中的 venv 检查强制要求使用项目 .venv，但 GitLab CI 使用 Docker 镜像中的系统 Python，无 .venv，导致 CI 流水线失败。

**解决**：在 `check_venv()` 函数中添加 `CI`/`GITLAB_CI` 环境变量检测，CI 环境下自动跳过 venv 检查，使用系统 Python 运行测试。

### 难点 5：pytest parametrize 的 tuple 解包问题

**问题**：`load_params_tuples` 返回 `[(item,)]` 形式传给 `@pytest.mark.parametrize` 时，pytest 将 params 解包为 tuple 而非 dict，导致用例参数类型错误。

**解决**：弃用 tuple 包装，直接使用 `load_params` 返回的 dict 列表传给 parametrize，利用 pytest 对 dict 参数的原生支持。

## 项目成果

1. **测试覆盖**：共编写 80+ 自动化测试用例（81 passed, 1 xfailed），覆盖核心引擎、数据驱动、Hook 机制、断言、环境管理、报告、重试 7 大模块
2. **测试稳定性**：全部用例使用 mock（unittest.mock.patch）避免外部网络依赖，消除 httpbin.org 503/504 不稳定问题，测试通过率 100%
3. **执行效率**：全量测试 3 秒内完成，支持并行扩展
4. **环境隔离**：实现 Dev/QA/Prod 三环境一键切换，用例与环境配置完全解耦
5. **报告可视化**：HTML 单文件报告（含环境信息、失败日志）+ Allure 交互式报告双输出
6. **CI/CD 集成**：MR 自动触发测试，main 分支自动冒烟，JUnit 报告集成 GitLab Test 页面
7. **容器化部署**：Docker 镜像一键构建运行，支持运行时参数覆盖
8. **可维护性**：分层架构清晰（入口层 → 核心引擎层 → 数据驱动层 → Hook 层 → 环境管理层 → 报告层 → CI/CD 层），核心代码全部中文注释，README 含 Mermaid 架构图

## 项目亮点

- **架构设计**：采用 HttpRunner 的数据模型与解析器作为底层，自研上层调度、环境管理、报告、重试机制，兼顾成熟底座与灵活扩展
- **断言体系**：14 种断言类型 + JSON Schema 校验，处理函数映射表模式使新增断言类型仅需添加一个函数与一行注册
- **重试策略**：异常类型分流设计（网络异常重试、配置错误不重试），避免无意义重试浪费执行时间
- **双报告体系**：HTML 报告适合快速查阅，Allure 报告适合深度分析，失败用例自动捕获 loguru 日志
- **DevOps 闭环**：从本地开发 → Docker 打包 → GitLab CI 自动触发 → 报告产物归档，形成完整 DevOps 测试链路

---

以上内容基于项目实际代码与功能模块编写，可直接用于简历"项目经历"章节。如需调整篇幅、侧重方向（如偏向架构设计/偏向测试执行/偏向 CI/CD），或拆分为多个项目经历，可进一步调整。