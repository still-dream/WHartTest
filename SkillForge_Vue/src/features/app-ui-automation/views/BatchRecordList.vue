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
      <a-button type="outline" @click="openConfig">
        <template #icon><icon-settings /></template>
        执行配置
      </a-button>
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

    <!-- 执行配置抽屉 -->
    <a-drawer
      v-model:visible="configVisible"
      title="执行配置"
      width="480px"
      unmount-on-close
      :footer="true"
    >
      <a-form :model="configForm" layout="vertical" :disabled="configLoading">
        <a-form-item label="图像匹配阈值" help="0-1 之间，值越低匹配越宽松">
          <a-input-number
            v-model="configForm.airtest_threshold"
            :min="0"
            :max="1"
            :step="0.05"
            :precision="2"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="元素查找超时（秒）">
          <a-input-number
            v-model="configForm.airtest_find_timeout"
            :min="1"
            :max="300"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="操作间隔延迟（秒）">
          <a-input-number
            v-model="configForm.airtest_opdelay"
            :min="0"
            :max="10"
            :step="0.1"
            :precision="1"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="Poco元素等待超时（秒）">
          <template #label>
            <span>Poco元素等待超时（秒）</span>
            <a-tag color="orange" size="small" style="margin-left: 8px">需重连生效</a-tag>
          </template>
          <a-input-number
            v-model="configForm.poco_wait_timeout"
            :min="1"
            :max="120"
            style="width: 100%"
          />
          <div v-if="configNeedsReconnect" style="margin-top: 8px">
            <a-alert type="warning" :show-icon="true">
              此参数已修改，下次执行脚本时将自动使用新值重新连接设备。
            </a-alert>
          </div>
        </a-form-item>
        <a-form-item v-if="configData.updated_by_name" label="最近更新">
          <span style="color: var(--color-text-3); font-size: 13px">
            {{ configData.updated_by_name }} · {{ formatTime(configData.updated_at) }}
          </span>
        </a-form-item>
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="configVisible = false">取消</a-button>
          <a-button type="primary" :loading="configSaving" @click="saveConfig">保存</a-button>
        </a-space>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconRefresh, IconEye, IconSettings } from '@arco-design/web-vue/es/icon'
import { batchRecordApi, executionConfigApi } from '../api'
import type { AppUiBatchExecutionRecord, AppUiBatchStatus, AppUiExecutionConfig } from '../types'
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

// ==================== 执行配置 ====================
const configVisible = ref(false)
const configLoading = ref(false)
const configSaving = ref(false)
const configData = reactive<AppUiExecutionConfig>({
  id: 1, airtest_threshold: 0.6, airtest_find_timeout: 30,
  airtest_opdelay: 1.0, poco_wait_timeout: 20,
  updated_by: null, updated_by_name: '', updated_at: '',
})
const configForm = reactive({
  airtest_threshold: 0.6,
  airtest_find_timeout: 30,
  airtest_opdelay: 1.0,
  poco_wait_timeout: 20,
})
const configNeedsReconnect = computed(() => configForm.poco_wait_timeout !== configData.poco_wait_timeout)

const openConfig = async () => {
  configVisible.value = true
  configLoading.value = true
  try {
    const res = await executionConfigApi.get()
    const data = extractResponseData<AppUiExecutionConfig>(res)
    if (data) {
      Object.assign(configData, data)
      Object.assign(configForm, {
        airtest_threshold: data.airtest_threshold,
        airtest_find_timeout: data.airtest_find_timeout,
        airtest_opdelay: data.airtest_opdelay,
        poco_wait_timeout: data.poco_wait_timeout,
      })
    }
  } catch {
    Message.error('获取执行配置失败')
  } finally {
    configLoading.value = false
  }
}

const saveConfig = async () => {
  configSaving.value = true
  try {
    const res = await executionConfigApi.update({
      airtest_threshold: configForm.airtest_threshold,
      airtest_find_timeout: configForm.airtest_find_timeout,
      airtest_opdelay: configForm.airtest_opdelay,
      poco_wait_timeout: configForm.poco_wait_timeout,
    })
    const data = extractResponseData<AppUiExecutionConfig & { needs_reconnect?: boolean }>(res)
    if (data) {
      Object.assign(configData, data)
      if (data.needs_reconnect) {
        Message.warning('配置已保存。Poco等待超时已修改，下次执行脚本时将自动重新连接设备生效。')
      } else {
        Message.success('配置已保存')
      }
      configVisible.value = false
    }
  } catch {
    Message.error('保存配置失败')
  } finally {
    configSaving.value = false
  }
}

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
