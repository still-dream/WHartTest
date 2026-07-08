<template>
  <div class="batch-record-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.status"
          placeholder="执行状态"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="(label, key) in APP_UI_BATCH_STATUS_LABELS" :key="key" :value="Number(key)">{{ label }}</a-option>
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
      :scroll="{ x: 1100 }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #status="{ record }">
        <a-tag :color="statusColors[record.status as AppUiBatchStatus]">
          {{ APP_UI_BATCH_STATUS_LABELS[record.status as AppUiBatchStatus] ?? '未知' }}
        </a-tag>
      </template>
      <template #trigger_type="{ record }">
        <a-tag :color="triggerColors[record.trigger_type]">
          {{ APP_UI_TRIGGER_LABELS[record.trigger_type] || record.trigger_type }}
        </a-tag>
      </template>
      <template #progress="{ record }">
        <span class="progress-text">
          成功 <span class="passed">{{ record.passed_scripts }}</span> /
          失败 <span class="failed">{{ record.failed_scripts }}</span> /
          总计 {{ record.total_scripts }}
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
          <a-button type="text" size="mini" @click="viewDetail(record)">
            <template #icon><icon-eye /></template>
            详情
          </a-button>
        </a-space>
      </template>
    </a-table>

    <!-- 详情抽屉 -->
    <a-drawer
      v-model:visible="drawerVisible"
      title="批量执行详情"
      width="720px"
      unmount-on-close
    >
      <template v-if="currentRecord">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="批次名称">{{ currentRecord.name }}</a-descriptions-item>
          <a-descriptions-item label="执行人">{{ currentRecord.executor_name ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="statusColors[currentRecord.status as AppUiBatchStatus]">
              {{ APP_UI_BATCH_STATUS_LABELS[currentRecord.status as AppUiBatchStatus] ?? '未知' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="触发类型">
            <a-tag :color="triggerColors[currentRecord.trigger_type]">
              {{ APP_UI_TRIGGER_LABELS[currentRecord.trigger_type] || currentRecord.trigger_type }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="脚本统计">
            成功: {{ currentRecord.passed_scripts }} / 失败: {{ currentRecord.failed_scripts }} / 总计: {{ currentRecord.total_scripts }}
          </a-descriptions-item>
          <a-descriptions-item label="执行时长">{{ currentRecord.duration?.toFixed(2) ?? '-' }}s</a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ currentRecord.start_time ? formatTime(currentRecord.start_time) : '-' }}</a-descriptions-item>
          <a-descriptions-item label="结束时间">{{ currentRecord.end_time ? formatTime(currentRecord.end_time) : '-' }}</a-descriptions-item>
        </a-descriptions>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconRefresh, IconEye } from '@arco-design/web-vue/es/icon'
import { batchRecordApi } from '../api'
import type { AppUiBatchExecutionRecord, AppUiBatchStatus } from '../types'
import {
  APP_UI_BATCH_STATUS_LABELS, APP_UI_TRIGGER_LABELS, extractPaginationData, extractResponseData,
} from '../types'

const loading = ref(false)
const recordData = ref<AppUiBatchExecutionRecord[]>([])
const drawerVisible = ref(false)
const currentRecord = ref<AppUiBatchExecutionRecord | null>(null)

const filters = reactive({
  status: undefined as number | undefined,
  trigger_type: undefined as string | undefined,
})
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const statusColors: Record<AppUiBatchStatus, string> = {
  0: 'gray',
  1: 'arcoblue',
  2: 'green',
  3: 'orange',
  4: 'red',
}

const triggerColors: Record<string, string> = {
  manual: 'arcoblue',
  scheduled: 'purple',
  api: 'cyan',
  debug: 'orange',
}

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '批次名称', dataIndex: 'name', ellipsis: true, tooltip: true, width: 220 },
  { title: '状态', slotName: 'status', width: 100, align: 'center' as const },
  { title: '触发类型', slotName: 'trigger_type', width: 100, align: 'center' as const },
  { title: '脚本统计', slotName: 'progress', width: 200, align: 'center' as const },
  { title: '时长', slotName: 'duration', width: 90, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 170, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 100, fixed: 'right' as const, align: 'center' as const },
]

const formatTime = (time: string) => {
  if (!time) return '-'
  const d = new Date(time)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const fetchRecords = async () => {
  loading.value = true
  try {
    const res = await batchRecordApi.list({
      status: filters.status,
      trigger_type: filters.trigger_type,
    })
    const { items, count } = extractPaginationData(res)
    recordData.value = items
    pagination.total = count
  } catch {
    Message.error('获取批量执行记录失败')
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

const viewDetail = async (record: AppUiBatchExecutionRecord) => {
  currentRecord.value = record
  drawerVisible.value = true
  try {
    const res = await batchRecordApi.get(record.id)
    const data = extractResponseData<AppUiBatchExecutionRecord>(res)
    if (data) {
      currentRecord.value = data
    }
  } catch {
    // 静默失败
  }
}

const refresh = () => fetchRecords()

defineExpose({ refresh })

onMounted(() => {
  fetchRecords()
})
</script>

<style scoped>
.batch-record-list {
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
.progress-text {
  font-size: 13px;
}
.progress-text .passed {
  color: rgb(var(--green-6));
  font-weight: 600;
}
.progress-text .failed {
  color: rgb(var(--red-6));
  font-weight: 600;
}
</style>
