-- 操作日志表创建SQL
-- 适用于PostgreSQL数据库
-- 执行方式: docker-compose exec postgres psql -U postgres -d wharttest -f /path/to/create_operation_logs_table.sql

-- 创建操作日志表
CREATE TABLE IF NOT EXISTS operation_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    username VARCHAR(150) NOT NULL,
    feature VARCHAR(200) NOT NULL,
    path VARCHAR(500),
    method VARCHAR(10),
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_operation_logs_user ON operation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_operation_logs_created_at ON operation_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_operation_logs_created_at_desc ON operation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_logs_user_created_at_desc ON operation_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_logs_username ON operation_logs(username);
CREATE INDEX IF NOT EXISTS idx_operation_logs_feature ON operation_logs(feature);

-- 添加外键约束（如果auth_user表存在）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'auth_user') THEN
        ALTER TABLE operation_logs 
        ADD CONSTRAINT fk_operation_logs_user 
        FOREIGN KEY (user_id) REFERENCES auth_user(id) 
        ON DELETE CASCADE;
    END IF;
END $$;

-- 添加表注释
COMMENT ON TABLE operation_logs IS '用户操作日志表 - 记录用户在系统中的操作访问记录';
COMMENT ON COLUMN operation_logs.id IS '主键ID';
COMMENT ON COLUMN operation_logs.user_id IS '用户ID（外键）';
COMMENT ON COLUMN operation_logs.username IS '用户名';
COMMENT ON COLUMN operation_logs.feature IS '功能点 - 用户访问的功能模块或页面';
COMMENT ON COLUMN operation_logs.path IS '访问路径';
COMMENT ON COLUMN operation_logs.method IS '请求方法（GET/POST/PUT/DELETE等）';
COMMENT ON COLUMN operation_logs.ip_address IS 'IP地址';
COMMENT ON COLUMN operation_logs.user_agent IS '用户代理（浏览器信息）';
COMMENT ON COLUMN operation_logs.created_at IS '访问时间';

-- 授权给web应用用户（如果需要）
-- GRANT SELECT, INSERT, UPDATE, DELETE ON operation_logs TO your_web_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_web_user;
