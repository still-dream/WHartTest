<template>
  <div class="execution-record-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.status"
          placeholder="执行状态"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="(label, key) in APP_UI_STATUS_LABELS" :key="key" :value="Number(key)">{{ label }}</a-option>
        </a-select>
        <a-select
          v-model="filters.trigger_type"
          placeholder="触发类型"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="(label, key) in APP_UI_TRIGGER_LABELS" :key="key" :value="key">{{ label }}</a-option>
        </a-select>
        <a-button type="outline" @click="onSearch">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="recordData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 1200 }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #status="{ record }">
        <a-tag :color="statusColors[record.status as AppUiExecutionStatus]">
          {{ APP_UI_STATUS_LABELS[record.status as AppUiExecutionStatus] ?? '未知' }}
        </a-tag>
      </template>
      <template #trigger_type="{ record }">
        <a-tag :color="triggerColors[record.trigger_type]">
          {{ APP_UI_TRIGGER_LABELS[record.trigger_type] || record.trigger_type }}
        </a-tag>
      </template>
      <template #steps="{ record }">
        <span class="step-stat">
          <span class="passed">{{ record.passed_steps }}</span> /
          <span class="failed">{{ record.failed_steps }}</span> /
          {{ record.total_steps }}
        </span>
      </template>
      <template #duration="{ record }">
        <span v-if="record.duration != null">{{ record.duration.toFixed(2) }}s</span>
        <span v-else>-</span>
      </template>
      <template #created_at="{ record }">
        <span>{{ formatTime(record.created_at) }}</span>
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button
            v-if="record.report_path"
            type="text"
            size="mini"
            @click="viewReport(record)"
          >
            <template #icon><icon-eye /></template>
            查看报告
          </a-button>
          <a-button
            v-if="record.report_path"
            type="text"
            size="mini"
            :loading="downloadingId === record.id"
            @click="downloadReport(record)"
          >
            <template #icon><icon-download /></template>
            下载
          </a-button>
          <a-popconfirm
            v-if="record.status === 1"
            content="确定取消该执行任务？"
            @ok="cancelExecution(record)"
          >
            <a-button type="text" size="mini" status="warning">
              <template #icon><icon-stop /></template>
              取消
            </a-button>
          </a-popconfirm>
          <a-button type="text" size="mini" @click="viewDetail(record)">
            <template #icon><icon-info-circle /></template>
            详情
          </a-button>
          <a-popconfirm content="确定删除该执行记录？" @ok="handleDelete(record.id)">
            <a-button type="text" size="mini" status="danger">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-table>

    <!-- 详情抽屉 -->
    <a-drawer
      v-model:visible="drawerVisible"
      title="执行记录详情"
      width="700px"
      unmount-on-close
    >
      <template v-if="currentRecord">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="脚本名称">{{ currentRecord.script_name ?? `ID: ${currentRecord.script}` }}</a-descriptions-item>
          <a-descriptions-item label="设备">{{ currentRecord.device_name ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行人">{{ currentRecord.executor_name ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="触发类型">
            <a-tag :color="triggerColors[currentRecord.trigger_type]">
              {{ APP_UI_TRIGGER_LABELS[currentRecord.trigger_type] || currentRecord.trigger_type }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="statusColors[currentRecord.status as AppUiExecutionStatus]">
              {{ APP_UI_STATUS_LABELS[currentRecord.status as AppUiExecutionStatus] ?? '未知' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="步骤统计">
            通过 {{ currentRecord.passed_steps }} / 失败 {{ currentRecord.failed_steps }} / 总计 {{ currentRecord.total_steps }}
          </a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ currentRecord.start_time ? formatTime(currentRecord.start_time) : '-' }}</a-descriptions-item>
          <a-descriptions-item label="结束时间">{{ currentRecord.end_time ? formatTime(currentRecord.end_time) : '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行时长">{{ currentRecord.duration != null ? `${currentRecord.duration.toFixed(2)}s` : '-' }}</a-descriptions-item>
          <a-descriptions-item label="Celery 任务">{{ currentRecord.celery_task_id || '-' }}</a-descriptions-item>
        </a-descriptions>

        <template v-if="currentRecord.error_message">
          <a-divider>错误信息</a-divider>
          <a-alert type="error" :title="currentRecord.error_message" />
        </template>

        <template v-if="currentRecord.execution_log">
          <a-divider>执行日志</a-divider>
          <pre class="log-content">{{ currentRecord.execution_log }}</pre>
        </template>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconRefresh, IconEye, IconDelete, IconDownload, IconStop, IconInfoCircle,
} from '@arco-design/web-vue/es/icon'
import { executionRecordApi } from '../api'
import type { AppUiExecutionRecord, AppUiExecutionStatus } from '../types'
import {
  APP_UI_STATUS_LABELS, APP_UI_TRIGGER_LABELS, extractPaginationData, extractResponseData,
} from '../types'

const loading = ref(false)
const recordData = ref<AppUiExecutionRecord[]>([])
const drawerVisible = ref(false)
const currentRecord = ref<AppUiExecutionRecord | null>(null)
const downloadingId = ref<number | null>(null)

const filters = reactive({
  status: undefined as number | undefined,
  trigger_type: undefined as string | undefined,
})
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const statusColors: Record<AppUiExecutionStatus, string> = {
  0: 'gray',
  1: 'arcoblue',
  2: 'green',
  3: 'red',
  4: 'orange',
}

const triggerColors: Record<string, string> = {
  manual: 'arcoblue',
  scheduled: 'purple',
  api: 'cyan',
  debug: 'orange',
}

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '脚本名称', dataIndex: 'script_name', ellipsis: true, tooltip: true, width: 200 },
  { title: '状态', slotName: 'status', width: 90, align: 'center' as const },
  { title: '触发类型', slotName: 'trigger_type', width: 100, align: 'center' as const },
  { title: '步骤(通/败/总)', slotName: 'steps', width: 130, align: 'center' as const },
  { title: '时长', slotName: 'duration', width: 90, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 170, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 320, fixed: 'right' as const, align: 'center' as const },
]

const formatTime = (time: string) => {
  if (!time) return '-'
  const d = new Date(time)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const hasRunning = computed(() => recordData.value.some((r) => r.status === 1))

const fetchRecords = async () => {
  loading.value = true
  try {
    const res = await executionRecordApi.list({
      status: filters.status,
      trigger_type: filters.trigger_type,
    })
    const { items, count } = extractPaginationData(res)
    recordData.value = items
    pagination.total = count
  } catch {
    Message.error('获取执行记录失败')
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchRecords()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchRecords()
}

const onPageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  fetchRecords()
}

const viewDetail = async (record: AppUiExecutionRecord) => {
  currentRecord.value = record
  drawerVisible.value = true
  try {
    const res = await executionRecordApi.get(record.id)
    const detail = extractResponseData<AppUiExecutionRecord>(res)
    if (detail) {
      currentRecord.value = detail
    }
  } catch {
    // 静默失败，使用列表数据
  }
}

const viewReport = async (record: AppUiExecutionRecord) => {
  try {
    const res = await executionRecordApi.fetchReport(record.id)
    const blob = new Blob([res.data], { type: 'text/html' })
    const blobUrl = URL.createObjectURL(blob)
    window.open(blobUrl, '_blank')
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60000)
  } catch {
    Message.error('打开报告失败')
  }
}

const downloadReport = async (record: AppUiExecutionRecord) => {
  downloadingId.value = record.id
  try {
    const res = await executionRecordApi.fetchDownload(record.id)
    const blob = new Blob([res.data], { type: 'application/octet-stream' })
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    const disposition = res.headers['content-disposition'] || ''
    const match = disposition.match(/filename="?(.+?)"?$/)
    link.download = match ? match[1] : `report_${record.id}.html`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(blobUrl)
  } catch {
    Message.error('下载报告失败')
  } finally {
    setTimeout(() => { downloadingId.value = null }, 2000)
  }
}

const cancelExecution = async (record: AppUiExecutionRecord) => {
  try {
    await executionRecordApi.cancel(record.id)
    Message.success('任务已取消')
    fetchRecords()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || '取消失败')
  }
}

const handleDelete = async (id: number) => {
  try {
    await executionRecordApi.delete(id)
    Message.success('删除成功')
    fetchRecords()
  } catch {
    Message.error('删除失败')
  }
}

// 轮询：当存在执行中（status=1）的记录时，每 3 秒刷新一次
let pollTimer: ReturnType<typeof setInterval> | null = null

const startPolling = () => {
  stopPolling()
  pollTimer = setInterval(() => {
    if (hasRunning.value) {
      fetchRecords()
    }
  }, 3000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const refresh = () => fetchRecords()

defineExpose({ refresh })

onMounted(() => {
  fetchRecords()
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.execution-record-list {
  padding: 16px;
  background: var(--color-bg-2);
  border-radius: 8px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.search-box {
  display: flex;
  align-items: center;
}
.step-stat {
  font-size: 13px;
}
.step-stat .passed {
  color: rgb(var(--green-6));
  font-weight: 600;
}
.step-stat .failed {
  color: rgb(var(--red-6));
  font-weight: 600;
}
.log-content {
  background: var(--color-fill-2);
  padding: 12px;
  border-radius: 4px;
  overflow: auto;
  max-height: 240px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
