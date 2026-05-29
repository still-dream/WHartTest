# ============================================
# 多阶段构建 - 优化后的Dockerfile
# 镜像大小：~1.1GB（从1.74GB减少36.8%）
# ============================================

ARG PYTHON_BASE_IMAGE=python:3.11-slim

# ============================================
# 第一阶段：构建阶段（包含编译工具）
# ============================================
FROM ${PYTHON_BASE_IMAGE} AS builder

ARG APT_BASE_URL=http://deb.debian.org
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_FALLBACKS=

WORKDIR /build

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_FALLBACKS=${PIP_INDEX_FALLBACKS}

# 安装构建依赖（仅在构建阶段需要）
RUN if [ "$APT_BASE_URL" != "http://deb.debian.org" ]; then \
        sed -i "s|http://deb.debian.org/debian|${APT_BASE_URL}/debian|g; s|http://deb.debian.org/debian-security|${APT_BASE_URL}/debian-security|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get -o Acquire::Retries=10 update && apt-get -o Acquire::Retries=10 install -y --fix-missing --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（主镜像失败时自动切换到后备源）
RUN set -eux; \
    install_uv() { \
      for index in "${PIP_INDEX_URL}" ${PIP_INDEX_FALLBACKS}; do \
        [ -n "$index" ] || continue; \
        echo "pip install uv via $index"; \
        if python -m pip install --no-cache-dir --retries 5 --timeout 30 -i "$index" uv; then \
          return 0; \
        fi; \
        echo "pip install uv failed via $index, trying next index..." >&2; \
      done; \
      return 1; \
    }; \
    install_uv

# 复制requirements并安装依赖到虚拟环境
COPY requirements.txt .

# 使用 uv 直接安装到虚拟环境（主镜像失败时自动切换到后备源）
RUN set -eux; \
    uv venv /opt/venv; \
    install_requirements() { \
      for index in "${PIP_INDEX_URL}" ${PIP_INDEX_FALLBACKS}; do \
        [ -n "$index" ] || continue; \
        echo "uv pip install via $index"; \
        if uv pip install --python /opt/venv/bin/python --no-cache \
          --default-index "$index" \
          -r requirements.txt; then \
          return 0; \
        fi; \
        echo "uv pip install failed via $index, trying next index..." >&2; \
      done; \
      return 1; \
    }; \
    install_requirements

# ============================================
# 第二阶段：运行阶段（仅包含运行时依赖）
# ============================================
FROM ${PYTHON_BASE_IMAGE}

ARG APT_BASE_URL=http://deb.debian.org
ARG HF_ENDPOINT=https://huggingface.co
ARG NPM_REGISTRY=https://registry.npmjs.org
ARG PLAYWRIGHT_DOWNLOAD_HOST=

WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FASTEMBED_CACHE_PATH=/root/.cache/fastembed \
    HF_ENDPOINT=${HF_ENDPOINT} \
    PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST} \
    HOME=/root \
    PYTHONPATH="/app:$PYTHONPATH"

# 安装系统依赖
RUN if [ "$APT_BASE_URL" != "http://deb.debian.org" ]; then \
        sed -i "s|http://deb.debian.org/debian|${APT_BASE_URL}/debian|g; s|http://deb.debian.org/debian-security|${APT_BASE_URL}/debian-security|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get -o Acquire::Retries=10 update && \
    apt-get -o Acquire::Retries=10 install -y --fix-missing --no-install-recommends \
    supervisor \
    curl \
    git \
    nodejs \
    npm \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    antiword \
    catdoc \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && fc-cache -fv

# 复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 确保虚拟环境的可执行文件被使用
ENV PATH="/opt/venv/bin:$PATH"

# 安装 Playwright 浏览器（在构建镜像时安装）
RUN npx playwright install chromium

# 复制 Python 项目文件（按顺序复制以优化缓存）
COPY manage.py ./
COPY wharttest_django/ /app/wharttest_django/
COPY accounts/ /app/accounts/
COPY projects/ /app/projects/
COPY testcases/ /app/testcases/
COPY langgraph_integration/ /app/langgraph_integration/
COPY mcp_tools/ /app/mcp_tools/
COPY api_keys/ /app/api_keys/
COPY knowledge/ /app/knowledge/
COPY prompts/ /app/prompts/
COPY requirements/ /app/requirements/
COPY orchestrator_integration/ /app/orchestrator_integration/
COPY skills/ /app/skills/
COPY testcase_templates/ /app/testcase_templates/
COPY ui_automation/ /app/ui_automation/
COPY weixin_integration/ /app/weixin_integration/
COPY task_center/ /app/task_center/

# 复制 Supervisor 配置
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 设置 Django 配置文件位置
ENV DJANGO_SETTINGS_MODULE=wharttest_django.settings

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /app/bundled_skills /root/.cache/fastembed

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 使用 Supervisor 启动服务
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]