#!/bin/bash

# 确保脚本在任何命令失败时退出
set -e

# 0. 安装新的Python依赖（如果有新增）
echo "Checking and installing new Python dependencies..."
if [ -f "/app/requirements.txt" ]; then
    # 确保pip已安装
    python -m ensurepip --upgrade 2>/dev/null || true
    # 安装依赖
    python -m pip install --no-cache-dir -r /app/requirements.txt 2>&1 | grep -v "Requirement already satisfied" || true
fi

# 1. 数据库迁移
echo "Applying database migrations..."
python manage.py migrate --noinput

# 2. 创建默认管理员用户
#    (使用 Dockerfile 中发现的 init_admin 命令)
echo "Creating default admin user if it does not exist..."
python manage.py init_admin

# 3. 启动 supervisord 来管理所有服务
echo "Starting supervisord..."
exec supervisord -c /app/supervisord.conf