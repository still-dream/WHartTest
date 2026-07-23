/**
 * APPUI 自动化 API 服务
 */

import request from '@/utils/request'
import { useAuthStore } from '@/store/authStore'
import { getCurrentServerLanguage } from '@/utils/installLocaleAdapters'
import type {
  AppUiModule,
  AppUiModuleForm,
  AppUiScript,
  AppUiDevice,
  AppUiDeviceForm,
  AppUiExecutionRecord,
  AppUiBatchExecutionRecord,
  AppUiExecutionConfig,
  AppUiScriptPreview,
  AppUiExecuteResult,
  AppUiDeviceCheckResult,
  PaginatedResponse,
} from '../types'

const BASE_URL = '/app-ui-automation'

/**
 * 使用原生 fetch 上传 FormData，绕过 axios 的 Content-Type 干扰。
 * 浏览器会自动为 FormData 设置正确的 multipart/form-data（含 boundary）。
 */
async function uploadViaFetch(url: string, method: string, data: FormData): Promise<any> {
  const baseURL = (request as any).defaults?.baseURL || '/api'
  const token = useAuthStore().getAccessToken
  const headers: Record<string, string> = {
    'Accept-Language': getCurrentServerLanguage(),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(`${baseURL}${url}`, { method, body: data, headers })

  let result: any
  try {
    result = await resp.json()
  } catch {
    throw {
      success: false,
      status: resp.status,
      error: `请求失败 (${resp.status} ${resp.statusText})`,
    }
  }

  if (!resp.ok) {
    throw {
      success: false,
      status: resp.status,
      error: result.message || '操作失败',
      errors: result.errors,
    }
  }
  return { success: true, data: result.data, message: result.message }
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

  /** 创建脚本（FormData 上传脚本文件，使用 fetch 绕过 axios Content-Type 问题） */
  create: (data: FormData) => uploadViaFetch(`${BASE_URL}/scripts/`, 'POST', data),

  /** 更新脚本（FormData 上传脚本文件，使用 fetch 绕过 axios Content-Type 问题） */
  update: (id: number, data: FormData) => uploadViaFetch(`${BASE_URL}/scripts/${id}/`, 'PATCH', data),

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

  /** 获取在线报告内容（Blob，通过 Authorization header 认证） */
  fetchReport: (id: number) =>
    request.get(`${BASE_URL}/execution-records/${id}/report/`, { responseType: 'blob' }),

  /** 下载报告内容（Blob，通过 Authorization header 认证） */
  fetchDownload: (id: number) =>
    request.get(`${BASE_URL}/execution-records/${id}/download/`, { responseType: 'blob' }),

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

// ==================== 执行配置管理 ====================
export const executionConfigApi = {
  get: () => request.get<AppUiExecutionConfig>(`${BASE_URL}/execution-config/1/`),

  update: (data: Partial<AppUiExecutionConfig>) =>
    request.patch<AppUiExecutionConfig & { needs_reconnect?: boolean }>(`${BASE_URL}/execution-config/1/`, data),
}
