#!/bin/bash
# =============================================================
# WHartTest 部署脚本（服务器端使用）
# =============================================================
# 用法：
#   ./deploy.sh                    # 拉最新代码 + 重建 + 重启
#   ./deploy.sh --no-build         # 只拉代码 + 重启（不重建镜像）
#   ./deploy.sh --logs             # 部署完成后查看日志
#   ./deploy.sh --clean            # 清理悬空镜像和旧数据
# =============================================================
set -e

# 配置
APP_DIR="/opt/wharttest"
BRANCH="${DEPLOY_BRANCH:-master}"
COMPOSE_FILE="docker-compose.yml"
# 优先用当前用户可写的日志位置，避免 /var/log 权限问题
LOG_FILE="${LOG_FILE:-$HOME/.wharttest-deploy.log}"

# 参数解析
DO_BUILD=1
SHOW_LOGS=0
DO_CLEAN=0
for arg in "$@"; do
    case $arg in
        --no-build) DO_BUILD=0 ;;
        --logs)     SHOW_LOGS=1 ;;
        --clean)    DO_CLEAN=1 ;;
        --help|-h)
            echo "用法: $0 [--no-build] [--logs] [--clean]"
            echo "  --no-build  只拉代码、重启，不重新构建镜像"
            echo "  --logs      部署完成后查看日志"
            echo "  --clean     清理悬空镜像"
            exit 0
            ;;
    esac
done

# 日志
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

echo ""
echo "============================================"
echo " WHartTest 部署开始: $(date '+%F %T')"
echo "============================================"

# 进入项目目录
cd "$APP_DIR"

# 0. 修复 .env 权限（如果存在但当前用户读不到）
if [ -f "$APP_DIR/.env" ] && [ ! -r "$APP_DIR/.env" ]; then
    echo "⚠️  .env 文件存在但当前用户读不到，尝试修复权限..."
    sudo chmod 644 "$APP_DIR/.env" 2>/dev/null || \
    sudo chown "$USER:$USER" "$APP_DIR/.env" 2>/dev/null || true
    if [ ! -r "$APP_DIR/.env" ]; then
        echo "❌ 无法读取 .env，请运行：sudo chown $USER:$USER $APP_DIR/.env"
        exit 1
    fi
fi

# 1. 拉取最新代码
echo ""
echo "[1/4] 拉取最新代码 (branch: $BRANCH)..."
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"
git clean -fd

LATEST_COMMIT=$(git rev-parse --short HEAD)
echo "  当前 commit: $LATEST_COMMIT"
echo "  commit 信息: $(git log -1 --pretty=%B | head -1)"

# 2. 重新构建镜像
if [ "$DO_BUILD" = "1" ]; then
    echo ""
    echo "[2/4] 重新构建镜像..."
    docker compose -f "$COMPOSE_FILE" build
else
    echo ""
    echo "[2/4] 跳过构建（--no-build）"
fi

# 3. 重启服务
echo ""
echo "[3/4] 重启服务..."
docker compose -f "$COMPOSE_FILE" up -d

# 4. 清理
if [ "$DO_CLEAN" = "1" ]; then
    echo ""
    echo "[4/4] 清理悬空镜像..."
    docker image prune -f
else
    echo ""
    echo "[4/4] 跳过清理"
fi

# 显示状态
echo ""
echo "============================================"
echo " 容器状态"
echo "============================================"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "============================================"
echo " 部署完成: $(date '+%F %T')"
echo "============================================"

# 查看日志
if [ "$SHOW_LOGS" = "1" ]; then
    echo ""
    echo "按 Ctrl+C 退出日志"
    sleep 2
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100
fi
