// 推送平台类型
export type PlatformType = 'feishu';

// 推送策略
export type PushConfig = 'always' | 'failure_only' | 'disabled';

// Webhook 地址
export interface WebhookAddress {
  id: number;
  name: string;
  url: string;
  platform_type: PlatformType;
  description: string;
  is_active: boolean;
  creator: number | null;
  created_at: string;
  updated_at: string;
}

// Webhook 地址精简版（普通用户可见）
export interface WebhookAddressLimited {
  id: number;
  name: string;
  is_active: boolean;
}

// Webhook 地址表单数据
export interface WebhookAddressFormData {
  name: string;
  url: string;
  platform_type?: PlatformType;
  description?: string;
  is_active?: boolean;
}

// 消息模板
export interface MessageTemplate {
  id: number;
  name: string;
  content: string;
  platform_type: PlatformType;
  description: string;
  is_system: boolean;
  creator: number | null;
  created_at: string;
  updated_at: string;
}

// 消息模板表单数据
export interface MessageTemplateFormData {
  name: string;
  content: string;
  platform_type?: PlatformType;
  description?: string;
}

// 变量定义
export interface NotificationVariable {
  name: string;
  description: string;
  example: string;
}

// 分页响应
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// 可用变量列表
export const NOTIFICATION_VARIABLES: NotificationVariable[] = [
  { name: 'task_name', description: '任务名称', example: '登录模块回归测试' },
  { name: 'project_name', description: '项目名称', example: 'J&T Express' },
  { name: 'status', description: '执行状态', example: '成功 / 失败' },
  { name: 'trigger_type', description: '触发方式', example: '定时 / 手动 / API' },
  { name: 'total', description: '用例总数', example: '15' },
  { name: 'passed', description: '通过数', example: '13' },
  { name: 'failed', description: '失败数', example: '2' },
  { name: 'pass_rate', description: '通过率', example: '86.7%' },
  { name: 'duration', description: '执行时长', example: '5分23秒' },
  { name: 'executor', description: '执行人', example: 'admin' },
  { name: 'failed_cases', description: '失败用例列表', example: 'test_login / test_payment' },
  { name: 'error_summary', description: '错误摘要', example: '2个用例执行失败' },
  { name: 'current_date', description: '当前日期时间', example: '2026-07-14 15:30:00' },
  { name: 'report_url', description: '报告链接', example: 'https://...' },
  { name: 'task_url', description: '任务详情链接', example: 'https://...' },
  { name: 'platform_name', description: '平台名称', example: 'WHartTest' },
];
