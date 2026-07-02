# 基础镜像：Python 3.10 精简版（与项目虚拟环境版本一致）
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量：禁用字节码缓存（减小镜像体积）、禁用输出缓冲（日志实时显示）
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 先单独拷贝依赖文件，利用 Docker 层缓存：依赖不变时不会重新安装
COPY requirements.txt .

# 安装依赖（使用阿里云镜像加速，适配国内网络环境）
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/

# 拷贝项目代码
COPY . .

# 创建报告输出目录
RUN mkdir -p reports

# 默认入口：运行全部测试并生成报告
# 可通过 docker run 覆盖参数，如：docker run <image> -m "api" --env qa
ENTRYPOINT ["python", "-m", "pytest"]

# 默认参数：运行所有测试，生成 HTML 报告
CMD ["--tb=short", "-q"]
