# 操作日志功能说明

## 功能概述

操作日志功能用于记录每个用户在什么时间访问了什么功能，支持按用户、功能点、时间进行筛选。

## 功能特性

### 1. 自动记录
- 通过中间件自动记录用户的访问行为
- 记录内容包括：用户、功能点、访问路径、请求方法、IP地址、访问时间
- 不记录静态资源请求（CSS、JS、图片等）
- 不记录认证失败和错误请求

### 2. 数据筛选
- **用户筛选**：按特定用户查看其操作记录
- **功能点筛选**：按功能模块查看访问记录
- **时间范围筛选**：选择日期范围查看特定时间段的记录
- **关键词搜索**：搜索用户名或功能点

### 3. 统计信息
- 总访问次数
- 今日访问次数
- 本周访问次数
- 本月访问次数
- 活跃用户数

### 4. 日志清理
- 管理员可以清理旧日志
- 支持自定义保留天数（默认30天）
- 防止日志数据无限增长

## 权限控制

- **普通用户**：只能查看自己的操作日志
- **管理员**：可以查看所有用户的操作日志，并执行清理操作

## 功能点映射

系统会自动将API路径映射为功能点：

| API路径 | 功能点名称 |
|---------|-----------|
| `/api/projects/` | 项目管理 |
| `/api/requirements/` | 需求管理 |
| `/api/testcases/` | 用例管理 |
| `/api/test-suites/` | 测试套件 |
| `/api/test-executions/` | 执行历史 |
| `/api/automation-scripts/` | UI脚本库 |
| `/api/knowledge/` | 知识库管理 |
| `/api/lg/` | LLM对话 |
| `/api/orchestrator/` | 智能编排 |
| `/api/prompts/` | 提示词管理 |
| `/api/accounts/users/` | 用户管理 |
| `/api/accounts/groups/` | 组织管理 |
| `/api/accounts/permissions/` | 权限管理 |
| `/api/llm-configs/` | LLM配置 |
| `/api/api-keys/` | KEY管理 |
| `/api/mcp_tools/` | MCP配置 |
| `/api/skills/` | Skills管理 |
| `/api/operation-logs/` | 操作日志 |

## API 接口

### 1. 获取操作日志列表
```
GET /api/accounts/operation-logs/
```

**查询参数：**
- `page`: 页码
- `page_size`: 每页数量
- `search`: 搜索关键词（用户名/功能点）
- `user`: 用户ID
- `feature`: 功能点
- `created_at_gte`: 开始时间
- `created_at_lte`: 结束时间

### 2. 获取统计信息
```
GET /api/accounts/operation-logs/statistics/
```

**返回数据：**
```json
{
  "total_count": 1000,
  "today_count": 50,
  "week_count": 200,
  "month_count": 500,
  "active_users": 20
}
```

### 3. 清理旧日志
```
DELETE /api/accounts/operation-logs/clear_old_logs/?days=30
```

**参数：**
- `days`: 保留最近多少天的日志（默认30天）

## 使用示例

### 前端调用示例

```typescript
// 获取操作日志
const response = await request({
  url: '/accounts/operation-logs/',
  method: 'GET',
  params: {
    page: 1,
    page_size: 20,
    user: 123,
    feature: '项目管理',
    created_at_gte: '2024-01-01T00:00:00Z',
    created_at_lte: '2024-12-31T23:59:59Z'
  }
});

// 获取统计信息
const stats = await request({
  url: '/accounts/operation-logs/statistics/',
  method: 'GET'
});

// 清理旧日志（仅管理员）
const result = await request({
  url: '/accounts/operation-logs/clear_old_logs/',
  method: 'DELETE',
  params: { days: 30 }
});
```

## 数据库表结构

```sql
CREATE TABLE operation_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    username VARCHAR(150) NOT NULL,
    feature VARCHAR(200) NOT NULL,
    path VARCHAR(500),
    method VARCHAR(10),
    ip_address VARCHAR(39),
    user_agent TEXT,
    created_at DATETIME NOT NULL,
    
    INDEX idx_user (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_created_at_desc (created_at DESC),
    INDEX idx_user_created (user_id, created_at DESC)
);
```

## 性能优化

1. **索引优化**：为常用查询字段添加索引
2. **分页查询**：支持分页，避免一次性加载大量数据
3. **异步记录**.：中间件异步记录，不影响请求响应速度
4. **定期清理**：建议设置定时任务定期清理旧日志

## 注意事项

1. **隐私保护**：操作日志包含用户访问信息，应妥善保护
2. **数据保留**：根据业务需求设置合理的日志保留期限
3. **性能影响**：日志记录会增加数据库写入，建议定期监控性能
4. **权限控制**：确保只有授权用户可以访问日志数据

## 扩展建议

1. **导出功能**：支持导出日志为Excel/CSV格式
2. **审计报告**：生成用户行为审计报告
3. **异常检测**：检测异常访问模式（如频繁访问敏感功能）
4. **可视化图表**：展示访问趋势和用户活跃度
