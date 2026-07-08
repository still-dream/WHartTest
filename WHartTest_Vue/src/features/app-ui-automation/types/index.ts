/**
 * APPUI 自动化类型定义
 */

/** APPUI 模块 */
export interface AppUiModule {
  id: number
  project: number
  name: string
  parent: number | null
  level: number
  children: AppUiModule[]
  creator: number | null
  creator_name: string
  created_at: string
  updated_at: string
}

/** APPUI 模块表单 */
export type AppUiModuleForm = Omit<AppUiModule, 'id' | 'level' | 'children' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>

/** 用例等级 */
export type AppUiCaseLevel = 'P0' | 'P1' | 'P2' | 'P3'

/** 脚本状态 */
export type AppUiScriptStatus = 'idle' | 'running' | 'success' | 'failed'

/** 平台 */
export type AppUiPlatform = 'android' | 'ios'

/** APPUI 脚本 */
export interface AppUiScript {
  id: number
  project: number
  module: number
  module_name: string
  name: string
  description: string | null
  platform: AppUiPlatform
  script_file: string
  script_dir: string
  script_entry: string
  level: AppUiCaseLevel
  status: AppUiScriptStatus
  creator: number | null
  creator_name: string
  created_at: string
  updated_at: string
}

/** 连接类型 */
export type AppUiConnectionType = 'adb_tcp' | 'emulator' | 'cloud' | 'usb'

/** 设备状态 */
export type AppUiDeviceStatus = 'online' | 'offline' | 'busy'

/** APPUI 设备 */
export interface AppUiDevice {
  id: number
  project: number
  name: string
  connection_type: AppUiConnectionType
  platform: AppUiPlatform
  device_uri: string
  device_serial: string
  status: AppUiDeviceStatus
  description: string | null
  is_default: boolean
  creator: number | null
  creator_name: string
  created_at: string
  updated_at: string
}

/** 设备表单 */
export type AppUiDeviceForm = Omit<AppUiDevice, 'id' | 'creator' | 'creator_name' | 'created_at' | 'updated_at'>

/** 执行状态: 0 等待中 | 1 执行中 | 2 成功 | 3 失败 | 4 取消 */
export type AppUiExecutionStatus = 0 | 1 | 2 | 3 | 4

export const APP_UI_STATUS_LABELS: Record<AppUiExecutionStatus, string> = {
  0: '等待中',
  1: '执行中',
  2: '成功',
  3: '失败',
  4: '取消',
}

/** 触发类型 */
export type AppUiTriggerType = 'manual' | 'scheduled' | 'api' | 'debug'

export const APP_UI_TRIGGER_LABELS: Record<string, string> = {
  manual: '手动',
  scheduled: '定时',
  api: 'API',
  debug: '调试',
}

/** 批量执行状态: 0 待执行 | 1 执行中 | 2 全部成功 | 3 部分失败 | 4 全部失败 */
export type AppUiBatchStatus = 0 | 1 | 2 | 3 | 4

export const APP_UI_BATCH_STATUS_LABELS: Record<AppUiBatchStatus, string> = {
  0: '待执行',
  1: '执行中',
  2: '全部成功',
  3: '部分失败',
  4: '全部失败',
}

/** APPUI 执行记录 */
export interface AppUiExecutionRecord {
  id: number
  batch: number | null
  script: number
  script_name: string
  device: number | null
  device_name: string
  status: AppUiExecutionStatus
  trigger_type: string
  executor: number | null
  executor_name: string
  total_steps: number
  passed_steps: number
  failed_steps: number
  report_path: string
  log_dir: string
  execution_log: string | null
  error_message: string | null
  start_time: string | null
  end_time: string | null
  duration: number | null
  celery_task_id: string
  created_at: string
}

/** APPUI 批量执行记录 */
export interface AppUiBatchExecutionRecord {
  id: number
  name: string
  total_scripts: number
  passed_scripts: number
  failed_scripts: number
  status: AppUiBatchStatus
  trigger_type: string
  executor: number | null
  executor_name: string
  start_time: string | null
  end_time: string | null
  duration: number | null
  created_at: string
}

/** 脚本预览结果 */
export interface AppUiScriptPreview {
  content: string
  entry: string
}

/** 执行结果 */
export interface AppUiExecuteResult {
  id: number
  status: number
  celery_task_id: string
  message: string
}

/** 设备检测结果 */
export interface AppUiDeviceCheckResult {
  status: AppUiDeviceStatus
  message: string
}

/** API 分页响应 */
export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

/** 响应拦截器包装格式 */
export interface ApiResponse<T> {
  success: boolean
  data: T
  message: string
}

/**
 * 提取 API 响应中的原始数据
 * 处理响应拦截器的多层嵌套包装:
 * - 一层: res.data = <actual_data>
 * - 两层: res.data = { data: <actual_data> }
 * - 三层: res.data = { data: { data: <actual_data> } }
 */
export function extractResponseData<T>(res: any): T | undefined {
  let data = res.data
  while (data && typeof data === 'object' && !Array.isArray(data) && 'data' in data) {
    data = data.data
  }
  return data
}

/**
 * 提取 API 响应中的数据列表
 * 处理响应拦截器的嵌套包装和分页/数组格式
 */
export function extractListData<T>(res: any): T[] {
  const wrapped = res.data?.data ?? res.data
  return wrapped?.results ?? (Array.isArray(wrapped) ? wrapped : [])
}

/**
 * 提取 API 响应中的分页信息
 */
export function extractPaginationData(res: any): { items: any[]; count: number } {
  const wrapped = res.data?.data ?? res.data
  if (wrapped?.results) {
    return { items: wrapped.results, count: wrapped.count ?? 0 }
  }
  const items = Array.isArray(wrapped) ? wrapped : []
  return { items, count: items.length }
}
