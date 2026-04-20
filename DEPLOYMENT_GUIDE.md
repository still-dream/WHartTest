# 操作日志功能部署指南 - Windows Docker

## 概述
本指南详细说明如何在 Windows 环境下使用 Docker 部署操作日志功能，包括前后端服务重新编译、重启以及数据库持久化配置。

## 前置要求
- Windows 10/11 专业版或企业版
- Docker Desktop for Windows 已安装并运行
- 项目代码已克隆到本地目录（如：c:\app\WHartTest）
- PowerShell 或 Git Bash 终端

---

## 一、数据库部署

### 1.1 PostgreSQL 数据库（推荐生产环境）

#### 方式一：使用 Django 自动迁移（推荐）
```powershell
# 进入项目目录
cd c:\app\WHartTest

# 启动数据库服务
docker-compose up -d postgres

# 等待数据库启动完成（约10-15秒）
Start-Sleep -Seconds 15

# 生成迁移文件
docker-compose exec backend python manage.py makemigrations accounts

# 执行迁移
docker-compose exec backend python manage.py migrate

# 验证表是否创建成功
docker-compose exec postgres psql -U postgres -d wharttest -c "\d operation_logs"
```

#### 方式二：使用 SQL 脚本手动创建
```powershell
# 进入项目目录
cd c:\app\WHartTest

# 启动数据库服务
docker-compose up -d postgres

# 等待数据库启动完成
Start-Sleep -Seconds 15

# 执行 SQL 脚本创建表
docker-compose exec -T postgres psql -U postgres -d wharttest < database/migrations/create_operation_logs_table.sql

# 验证表是否创建成功
docker-compose exec postgres psql -U postgres -d wharttest -c "\d operation_logs"
```

### 1.2 SQLite 数据库（开发环境）

```powershell
# 进入项目目录
cd c:\app\WHartTest

# 设置环境变量使用 SQLite
$env:DATABASE_TYPE="sqlite"

# 生成迁移文件
docker-compose exec backend python manage.py makemigrations accounts

# 执行迁移
docker-compose exec backend python manage.py migrate

# 验证表是否创建成功
docker-compose exec backend python manage.py dbshell "SELECT name FROM sqlite_master WHERE type='table' AND name='operation_logs';"
```

---

## 二、后端服务部署

### 2.1 重新构建后端镜像
```powershell
# 进入项目目录
cd c:\app\WHartTest

# 停止并删除旧的后端容器
docker-compose stop backend
docker-compose rm -f backend

# 重新构建后端镜像（无缓存）
docker-compose build --no-cache backend

# 启动后端服务
docker-compose up -d backend

# 查看后端日志，确认启动成功
docker-compose logs -f backend
```

### 2.2 验证后端服务
```powershell
# 检查后端容器状态
docker-compose ps backend

# 测试 API 端点
curl http://localhost:8912/api/operation-logs/

# 查看后端日志
docker-compose logs --tail=50 backend
```

---

## 三、前端服务部署

### 3.1 重新构建前端镜像
```powershell
# 进入项目目录
cd c:\app\WHartTest

# 停止并删除旧的前端容器
docker-compose stop frontend
docker-compose rm -f frontend

# 重新构建前端镜像（无缓存）
docker-compose build --no-cache frontend

# 启动前端服务
docker-compose up -d frontend

# 查看前端日志，确认启动成功
docker-compose logs -f frontend
```

### 3.2 验证前端服务
```powershell
# 检查前端容器状态
docker-compose ps frontend

# 测试前端页面
curl http://localhost:8913/

# 在浏览器中访问
# http://localhost:8913
```

---

## 四、完整部署流程（一键部署）

### 4.1 完整重新部署所有服务
```powershell
# 进入项目目录
cd c:\app\WHartTest

# 停止所有服务
docker-compose down

# 重新构建所有镜像（无缓存）
docker-compose build --no-cache

# 启动所有服务
docker-compose up -d

# 等待服务启动
Start-Sleep -Seconds 30

# 执行数据库迁移
docker-compose exec backend python manage.py makemigrations accounts
docker-compose exec backend python manage.py migrate

# 查看所有服务状态
docker-compose ps
```

### 4.2 仅重新部署操作日志相关服务
```powershell
# 进入项目目录
cd c:\app\WHartTest

# 停止后端和前端服务
docker-compose stop backend frontend

# 重新构建后端和前端
docker-compose build --no-cache backend frontend

# 启动后端和前端
docker-compose up -d backend frontend

# 等待服务启动
Start-Sleep -Seconds 20

# 执行数据库迁移
docker-compose exec backend python manage.py makemigrations accounts
docker-compose exec backend python manage.py migrate

# 查看服务状态
docker-compose ps backend frontend
```

---

## 五、数据持久化配置

### 5.1 PostgreSQL 数据持久化

PostgreSQL 数据已通过 Docker volumes 自动持久化：

```yaml
# docker-compose.yml 中的配置
volumes:
  - postgres-data:/var/lib/postgresql/data

volumes:
  postgres-data:  # 命名卷，由 Docker 管理
```

**持久化位置：**
- Windows: `\\wsl$\docker-desktop-data\data\docker\volumes\wharttest_postgres-data\_data`
- 或通过 Docker Desktop 查看：Settings > Resources > Volumes

**备份 PostgreSQL 数据：**
```powershell
# 备份数据库到本地文件
docker-compose exec postgres pg_dump -U postgres wharttest > backup_wharttest_$(Get-Date -Format "yyyyMMdd_HHmmss").sql

# 恢复数据库
docker-compose exec -T postgres psql -U postgres wharttest < backup_wharttest_20250414_120000.sql
```

### 5.2 SQLite 数据持久化

SQLite 数据通过本地目录挂载持久化：

```yaml
# docker-compose.yml 中的配置
volumes:
  - ./data:/app/data
```

**持久化位置：**
- Windows: `c:\app\WHartTest\data\db.sqlite3`

**备份 SQLite 数据：**
```powershell
# 复制数据库文件
Copy-Item c:\app\WHartTest\data\db.sqlite3 c:\app\WHartTest\backup\db.sqlite3_$(Get-Date -Format "yyyyMMdd_HHmmss")
```

### 5.3 其他数据持久化

项目中的其他数据也已配置持久化：

| 数据类型 | 持久化方式 | 位置 |
|---------|-----------|------|
| PostgreSQL 数据 | Docker Volume | Docker 管理的命名卷 |
| Redis 数据 | Docker Volume | redis-data |
| Qdrant 向量数据 | Docker Volume | qdrant-data |
| Xinference 模型数据 | Docker Volume | xinference-data |
| 媒体文件 | 本地目录挂载 | ./data/media |
| Playwright 截图 | 本地目录挂载 | ./data/playwright-screenshots |

---

## 六、验证部署

### 6.1 检查所有服务状态
```powershell
# 查看所有容器状态
docker-compose ps

# 预期输出：所有服务状态为 "Up" 或 "Up (healthy)"
```

### 6.2 测试操作日志 API
```powershell
# 获取操作日志列表（需要认证）
curl -X GET http://localhost:8912/api/operation-logs/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 获取操作日志统计
curl -X GET http://localhost:8912/api/operation-logs/statistics/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 6.3 测试前端页面
```powershell
# 在浏览器中访问以下地址：
# http://localhost:8913 - 主页面
# 登录后，在系统管理模块下应该能看到"操作日志"菜单
```

### 6.4 检查数据库表
```powershell
# PostgreSQL
docker-compose exec postgres psql -U postgres -d wharttest -c "\d operation_logs"

# SQLite
docker-compose exec backend python manage.py dbshell "PRAGMA table_info(operation_logs);"
```

---

## 七、常见问题排查

### 7.1 迁移失败
```powershell
# 查看详细错误信息
docker-compose exec backend python manage.py migrate --verbosity 3

# 如果遇到冲突，可以重置迁移
docker-compose exec backend python manage.py migrate accounts zero
docker-compose exec backend python manage.py makemigrations accounts
docker-compose exec backend python manage.py migrate
```

### 7.2 容器启动失败
```powershell
# 查看容器日志
docker-compose logs backend
docker-compose logs frontend

# 检查端口占用
netstat -ano | findstr "8912"
netstat -ano | findstr "8913"
```

### 7.3 数据库连接失败
```powershell
# 检查数据库容器状态
docker-compose ps postgres

# 测试数据库连接
docker-compose exec postgres psql -U postgres -d wharttest -c "SELECT 1;"
```

### 7.4 前端无法访问后端
```powershell
# 检查网络连接
docker-compose exec backend curl http://localhost:8000/api/

# 检查 CORS 配置
docker-compose exec backend env | findstr CORS
```

---

## 八、维护操作

### 8.1 清理旧日志
```powershell
# 清理30天前的日志（需要管理员权限）
curl -X DELETE "http://localhost:8912/api/operation-logs/clear_old_logs/?days=30" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### 8.2 查看日志统计
```powershell
# 获取操作日志统计信息
curl -X GET "http://localhost:8912/api/operation-logs/statistics/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 8.3 更新代码后重新部署
```powershell
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build backend frontend

# 执行迁移
docker-compose exec backend python manage.py migrate
```

---

## 九、快速参考

### 常用命令
```powershell
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f [service_name]

# 重新构建服务
docker-compose build --no-cache [service_name]

# 执行数据库迁移
docker-compose exec backend python manage.py migrate

# 进入后端容器
docker-compose exec backend bash

# 进入数据库容器
docker-compose exec postgres psql -U postgres -d wharttest
```

### 服务端口
| 服务 | 端口 | 访问地址 |
|------|------|---------|
| PostgreSQL | 8919 | localhost:8919 |
| Redis | 8911 | localhost:8911 |
| Backend API | 8912 | http://localhost:8912 |
| Frontend | 8913 | http://localhost:8913 |
| MCP Service | 8914 | http://localhost:8914 |
| Playwright MCP | 8916 | http://localhost:8916 |
| Qdrant | 8918 | http://localhost:8918 |
| Xinference | 8917 | http://localhost:8917 |
| Draw.io | 8920 | http://localhost:8920 |

---

## 十、安全建议

1. **修改默认密码**
   - 修改 `.env` 文件中的数据库密码
   - 修改 Django 管理员密码
   - 修改 JWT 密钥

2. **配置防火墙**
   - 仅开放必要的端口
   - 使用反向代理（如 Nginx）

3. **启用 HTTPS**
   - 配置 SSL 证书
   - 强制使用 HTTPS

4. **定期备份**
   - 设置自动备份脚本
   - 备份到远程存储

5. **监控日志**
   - 定期检查操作日志
   - 设置异常告警

---

## 联系支持

如遇到问题，请检查：
1. Docker Desktop 是否正常运行
2. 所有服务是否正常启动
3. 端口是否被占用
4. 网络连接是否正常
5. 查看容器日志获取详细错误信息
