/**
 * APPUI 自动化 API 服务
 */

import request from '@/utils/request'
import type {
  AppUiModule,
  AppUiModuleForm,
  AppUiScript,
  AppUiDevice,
  AppUiDeviceForm,
  AppUiExecutionRecord,
  AppUiBatchExecutionRecord,
  AppUiScriptPreview,
  AppUiExecuteResult,
  AppUiDeviceCheckResult,
  PaginatedResponse,
} from '../types'

const BASE_URL = '/app-ui-automation'

// 拼接可直接在浏览器中打开的完整 URL（基于 axios 实例的 baseURL）
function buildUrl(path: string): string {
  const baseURL = (request as any).defaults?.baseURL || ''
  return `${baseURL}${path}`
}

// ==================== 模块管理 ====================
export const moduleApi = {
  list: (params?: { project?: number; parent?: number; level?: number }) =>
    request.get<PaginatedResponse<AppUiModule>>(`${BASE_URL}/modules/`, { params }),

  tree: (projectId: number) =>
    request.get<AppUiModule[]>(`${BASE_URL}/modules/tree/`, { params: { project: projectId } }),

  get: (id: number) => request.get<AppUiModule>(`${BASE_URL}/modules/${id}/`),

  create: (data: AppUiModuleForm) => request.post<AppUiModule>(`${BASE_URL}/modules/`, data),

  update: (id: number, data: Partial<AppUiModuleForm>) =>
    request.patch<AppUiModule>(`${BASE_URL}/modules/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/modules/${id}/`),
}

// ==================== 脚本管理 ====================
export const scriptApi = {
  list: (params?: { project?: number; module?: number; platform?: string; status?: string; search?: string }) =>
    request.get<PaginatedResponse<AppUiScript>>(`${BASE_URL}/scripts/`, { params }),

  get: (id: number) => request.get<AppUiScript>(`${BASE_URL}/scripts/${id}/`),

  /** 创建脚本（FormData 上传 zip 文件） */
  create: (data: FormData) =>
    request.post<AppUiScript>(`${BASE_URL}/scripts/`, data, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  /** 更新脚本（FormData 上传 zip 文件） */
  update: (id: number, data: FormData) =>
    request.patch<AppUiScript>(`${BASE_URL}/scripts/${id}/`, data, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  delete: (id: number) => request.delete(`${BASE_URL}/scripts/${id}/`),

  /** 预览脚本源码 */
  preview: (id: number) =>
    request.get<AppUiScriptPreview>(`${BASE_URL}/scripts/${id}/preview/`),

  /** 执行脚本（调试） */
  execute: (id: number, data: { device_id?: number; trigger_type?: string }) =>
    request.post<AppUiExecuteResult>(`${BASE_URL}/scripts/${id}/execute/`, data),
}

// ==================== 设备管理 ====================
export const deviceApi = {
  list: (params?: { project?: number; platform?: string; connection_type?: string; status?: string; search?: string }) =>
    request.get<PaginatedResponse<AppUiDevice>>(`${BASE_URL}/devices/`, { params }),

  get: (id: number) => request.get<AppUiDevice>(`${BASE_URL}/devices/${id}/`),

  create: (data: AppUiDeviceForm) => request.post<AppUiDevice>(`${BASE_URL}/devices/`, data),

  update: (id: number, data: Partial<AppUiDeviceForm>) =>
    request.patch<AppUiDevice>(`${BASE_URL}/devices/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/devices/${id}/`),

  /** 检测设备连接状态 */
  check: (id: number) =>
    request.post<AppUiDeviceCheckResult>(`${BASE_URL}/devices/${id}/check/`),
}

// ==================== 执行记录管理 ====================
export const executionRecordApi = {
  list: (params?: { script?: number; device?: number; status?: number; trigger_type?: string }) =>
    request.get<PaginatedResponse<AppUiExecutionRecord>>(`${BASE_URL}/execution-records/`, { params }),

  get: (id: number) => request.get<AppUiExecutionRecord>(`${BASE_URL}/execution-records/${id}/`),

  delete: (id: number) => request.delete(`${BASE_URL}/execution-records/${id}/`),

  /** 获取在线报告的访问 URL */
  reportUrl: (id: number) => buildUrl(`${BASE_URL}/execution-records/${id}/report/`),

  /** 获取报告下载 URL */
  downloadUrl: (id: number) => buildUrl(`${BASE_URL}/execution-records/${id}/download/`),

  /** 取消执行 */
  cancel: (id: number) =>
    request.post(`${BASE_URL}/execution-records/${id}/cancel/`),
}

// ==================== 批量执行记录管理 ====================
export const batchRecordApi = {
  list: (params?: { status?: number; trigger_type?: string }) =>
    request.get<PaginatedResponse<AppUiBatchExecutionRecord>>(`${BASE_URL}/batch-records/`, { params }),

  get: (id: number) => request.get<AppUiBatchExecutionRecord>(`${BASE_URL}/batch-records/${id}/`),
}
