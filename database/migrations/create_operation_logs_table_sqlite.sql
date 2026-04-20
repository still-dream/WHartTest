-- 操作日志表创建SQL
-- 适用于SQLite数据库
-- 执行方式: docker-compose exec backend python manage.py dbshell < /path/to/create_operation_logs_table_sqlite.sql
-- 或者: sqlite3 data/db.sqlite3 < create_operation_logs_table_sqlite.sql

-- 创建操作日志表
CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username VARCHAR(150) NOT NULL,
    feature VARCHAR(200) NOT NULL,
    path VARCHAR(500),
    method VARCHAR(10),
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_operation_logs_user ON operation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_operation_logs_created_at ON operation_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_operation_logs_username ON operation_logs(username);
CREATE INDEX IF NOT EXISTS idx_operation_logs_feature ON operation_logs(feature);
