# 多阶段构建：减小最终镜像体积
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 最终镜像
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（运行时）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 复制已安装的包
COPY --from=builder /root/.local /root/.local

# 复制源代码
COPY . .

# 确保 PATH 包含用户目录的 bin（如果有 console scripts）
ENV PATH=/root/.local/bin:$PATH

# 暴露端口
EXPOSE 9999

# 使用 gunicorn + uvicorn workers 运行，增加稳定性
# 端口通过环境变量 BACKEND_PORT 覆盖，默认 9999
CMD gunicorn main:app --bind 0.0.0.0:${BACKEND_PORT:-9999} --workers 4 --worker-class uvicorn.workers.UvicornWorker --access-logfile -
