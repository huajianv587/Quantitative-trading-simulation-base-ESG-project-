# 多阶段构建：减小镜像大小
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .

# 安装依赖到虚拟环境
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir setuptools && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ────────────────────────────────────────────────────────────────────
# 最终镜像
FROM python:3.11-slim

WORKDIR /app

# 从 builder 阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 复制应用代码
COPY . .

# 设置环境变量
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PYTHONPATH=/app \
    HF_HOME=/root/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health/ready').raise_for_status()" || exit 1

WORKDIR /app
CMD ["sh", "-c", "uvicorn gateway.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
