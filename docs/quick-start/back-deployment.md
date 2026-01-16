# 🏢 后端部署指南

本指南将引导您完成 WHartTest 后端服务的生产环境部署。系统已改为使用API方式调用嵌入模型，无需本地下载模型文件。

## 📊 数据库配置

系统支持两种数据库：
- **PostgreSQL**（默认）：生产环境推荐，支持高并发
- **qdrant**：开源的高性能向量数据库

### 使用 PostgreSQL（默认）

1. **安装 PostgreSQL**
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib

# 启动服务
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

2. **创建数据库和用户**
```bash
# 切换到 postgres 用户
sudo -u postgres psql

# 在 PostgreSQL 中执行
CREATE DATABASE wharttest;
CREATE USER wharttest_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE wharttest TO wharttest_user;
\q
```

3. **配置环境变量**
```bash
# 设置数据库类型为 PostgreSQL
export DATABASE_TYPE=postgres
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=wharttest
export POSTGRES_USER=wharttest_user
export POSTGRES_PASSWORD=your_secure_password
```

4. **执行数据库迁移**
```bash
python manage.py migrate
```

## 部署qdrant向量数据库服务
```bash
docker-compose up -d qdrant
```

---

### 🛠️ 后端部署


#### 1. 系统准备
首先，安装 `uv`，一个先进的 Python 包管理器。
```bash
# 安装 uv (以 Ubuntu 为例)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 将 uv 添加到当前会话的 PATH
source $HOME/.cargo/env

# windows安装uv
pip install uv
# 注意：为了永久生效，请将 `source $HOME/.cargo/env` 添加到您的 shell 配置文件中 (如 ~/.bashrc 或 ~/.zshrc)
```

#### 2. 克隆项目
```bash
git clone https://github.com/MGdaasLab/WHartTest.git
cd WHartTest/WHartTest_Django
```

#### 3. 创建并激活虚拟环境
使用 `uv` 创建并激活一个基于 Python 3.11 的虚拟环境。
```bash
# 使用 Python 3.11 创建虚拟环境
uv venv --python 3.11 

# 激活虚拟环境
source .venv/bin/activate
```

#### 4. 安装依赖
使用 `uv` 高效地安装项目依赖。
```bash
uv pip install -r requirements.txt
```

#### 5. 数据库迁移和初始化
```bash
# 执行数据库迁移
uv run python manage.py migrate
# 初始化数据库
uv run python manage.py init_admin
```

#### 6. 启动服务
```bash
# 开发环境启动
uv run uvicorn wharttest_django.asgi:application --reload --host 127.0.0.1 --port 8000
```