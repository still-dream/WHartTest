# ============================================
# 多阶段构建 - 优化后的Dockerfile
# 镜像大小：~1.1GB（从1.74GB减少36.8%）
# ============================================

# ============================================
# 第一阶段：构建阶段（包含编译工具）
# ============================================
FROM docker.m.daocloud.io/library/python:3.11-slim AS builder

WORKDIR /build

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装构建依赖（仅在构建阶段需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装uv（更快的pip替代品）
RUN pip install --no-cache-dir uv

# 复制requirements并安装依赖到虚拟环境
COPY requirements.txt .

# 使用uv直接安装到虚拟环境（uv更快）
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python --no-cache -r requirements.txt

# 预下载 BM25 稀疏编码模型（用于混合检索）
# 使用 FASTEMBED_CACHE_PATH 环境变量强制指定缓存路径
ENV HOME=/root \
    FASTEMBED_CACHE_PATH=/root/.cache/fastembed
RUN mkdir -p /root/.cache/fastembed && \
    /opt/venv/bin/python -c "\
import os; \
os.environ['FASTEMBED_CACHE_PATH'] = '/root/.cache/fastembed'; \
from fastembed import SparseTextEmbedding; \
m = SparseTextEmbedding('Qdrant/bm25'); \
print('BM25 model downloaded to:', os.environ.get('FASTEMBED_CACHE_PATH')); \
" && ls -la /root/.cache/fastembed/

# ============================================
# 第二阶段：运行阶段（仅包含运行时依赖）
# ============================================
FROM docker.m.daocloud.io/library/python:3.11-slim

WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# 仅安装运行时必需的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从构建阶段复制虚拟环境（不包含构建工具）
COPY --from=builder /opt/venv /opt/venv

# 从构建阶段复制预下载的 BM25 模型缓存
COPY --from=builder /root/.cache/fastembed /root/.cache/fastembed

# 复制启动脚本和配置文件
COPY entrypoint.sh /app/entrypoint.sh
COPY supervisord.conf /app/supervisord.conf

# 转换换行符并添加执行权限
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# 复制Django项目代码（仅复制必要的Python代码）
COPY manage.py /app/
COPY accounts/ /app/accounts/
COPY api_keys/ /app/api_keys/
COPY knowledge/ /app/knowledge/
COPY langgraph_integration/ /app/langgraph_integration/
COPY mcp_tools/ /app/mcp_tools/
COPY orchestrator_integration/ /app/orchestrator_integration/
COPY projects/ /app/projects/
COPY prompts/ /app/prompts/
COPY requirements/ /app/requirements/
COPY testcases/ /app/testcases/
COPY wharttest_django/ /app/wharttest_django/

# 清理不必要的文件
RUN find /app -type f \( -name "*.sqlite*" -o -name "*.db" -o -name "*.sql" \) -delete && \
    find /app -type d \( -name ".venv" -o -name "venv" -o -name "__pycache__" -o -name ".git" -o -name "*.egg-info" \) -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyo" -delete 2>/dev/null || true

# 创建必要的目录
RUN mkdir -p media static nltk_data /var/log

# 暴露端口
EXPOSE 8000

# 设置启动脚本为入口点
ENTRYPOINT ["/app/entrypoint.sh"]