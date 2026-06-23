// 操作日志服务：封装后端 /api/accounts/operation-logs/ 的查询与清理接口。
import { request } from '@/utils/request';

export interface OperationLog {
  id: number;
  user: number;
  username: string;
  user_email?: string;
  feature: string;
  path: string;
  method: string;
  ip_address: string;
  user_agent: string;
  created_at: string;
}

export interface OperationLogListParams {
  page?: number;
  page_size?: number;
  // 筛选条件
  user?: number;
  username?: string;
  feature?: string;
  // 日期范围筛选（ISO 字符串）
  created_at__gte?: string;
  created_at__lte?: string;
  // 模糊搜索
  search?: string;
  ordering?: string;
}

export interface OperationLogStatistics {
  total_count: number;
  today_count: number;
  week_count: number;
  month_count: number;
  active_users: number;
}

const BASE_URL = '/accounts/operation-logs';

export const operationLogService = {
  /** 分页查询操作日志 */
  async list(params: OperationLogListParams = {}) {
    return request<OperationLog[]>({
      url: `${BASE_URL}/`,
      method: 'GET',
      params,
    });
  },

  /** 获取统计信息 */
  async statistics() {
    return request<OperationLogStatistics>({
      url: `${BASE_URL}/statistics/`,
      method: 'GET',
    });
  },

  /** 清理指定天数之前的旧日志（仅管理员） */
  async clearOldLogs(days = 30) {
    return request<{ message: string; deleted_count: number }>({
      url: `${BASE_URL}/clear_old_logs/`,
      method: 'DELETE',
      params: { days },
    });
  },
};
