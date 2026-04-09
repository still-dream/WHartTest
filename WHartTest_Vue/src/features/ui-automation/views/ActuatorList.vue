<template>
  <div class="actuator-list">
    <!-- 头部 -->
    <div class="header">
      <div class="title">
        <h3>{{ pageText.title }}</h3>
        <span class="count">{{ pageText.count(actuators.length) }}</span>
      </div>
      <div class="actions">
        <a-button @click="loadActuators" :loading="loading">
          <template #icon><icon-refresh /></template>
          {{ pageText.refresh }}
        </a-button>
      </div>
    </div>

    <!-- 状态提示 -->
    <a-alert
      v-if="!loading && actuators.length === 0"
      type="warning"
      class="mb-4"
    >
      <template #title>{{ pageText.emptyTitle }}</template>
      {{ pageText.startServiceHint }}
    </a-alert>

    <!-- 执行器表格 -->
    <a-table
      :key="`actuator-table-${locale}`"
      :data="actuators"
      :loading="loading"
      :pagination="false"
      stripe
    >
      <template #columns>
        <a-table-column :title="pageText.status" :width="70" align="center">
          <template #cell>
            <div class="online-dot"></div>
          </template>
        </a-table-column>
        <a-table-column :title="pageText.name" data-index="name" :width="160" />
        <a-table-column :title="pageText.ipAddress" data-index="ip" :width="150" />
        <a-table-column :title="pageText.type" :width="100">
          <template #cell="{ record }">
            <a-tag :color="getTypeTagColor(record.type)" size="small">
              {{ getTypeLabel(record.type) }}
            </a-tag>
          </template>
        </a-table-column>
        <a-table-column :title="pageText.browser" data-index="browser_type" :width="100" />
        <a-table-column :title="pageText.headlessMode" :width="90" align="center">
          <template #cell="{ record }">
            <a-tag :color="record.headless ? 'orangered' : 'green'" size="small">
              {{ record.headless ? pageText.yes : pageText.no }}
            </a-tag>
          </template>
        </a-table-column>
        <a-table-column title="OPEN" :width="80" align="center">
          <template #cell="{ record }">
            <a-switch v-model="record.is_open" size="small" disabled />
          </template>
        </a-table-column>
        <a-table-column title="DEBUG" :width="80" align="center">
          <template #cell="{ record }">
            <a-switch v-model="record.debug" size="small" disabled />
          </template>
        </a-table-column>
        <a-table-column :title="pageText.connectedAt" :width="170">
          <template #cell="{ record }">
            <span class="time-text">{{ formatTime(record.connected_at) }}</span>
          </template>
        </a-table-column>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { IconRefresh } from '@arco-design/web-vue/es/icon'
import { useAppI18n } from '@/composables/useAppI18n'
import { actuatorApi, type ActuatorInfo } from '../api'
import { extractResponseData } from '../types'

void IconRefresh

const { locale, isEnglish } = useAppI18n()

const pageText = computed(() => (
  isEnglish.value
    ? {
        title: 'Online actuators',
        count: (count: number) => `${count} total`,
        refresh: 'Refresh',
        emptyTitle: 'No online actuators',
        startServiceHint: 'Start the actuator service first: cd WHartTest_Actuator && python main.py',
        status: 'Status',
        name: 'Name',
        ipAddress: 'IP address',
        type: 'Type',
        browser: 'Browser',
        headlessMode: 'Headless',
        yes: 'Yes',
        no: 'No',
        connectedAt: 'Connected at',
      }
    : {
        title: '在线执行器',
        count: (count: number) => `共 ${count} 个`,
        refresh: '刷新',
        emptyTitle: '暂无在线执行器',
        startServiceHint: '请先启动执行器服务：cd WHartTest_Actuator && python main.py',
        status: '状态',
        name: '名称',
        ipAddress: 'IP地址',
        type: '类型',
        browser: '浏览器',
        headlessMode: '无头模式',
        yes: '是',
        no: '否',
        connectedAt: '连接时间',
      }
))

const actuators = ref<ActuatorInfo[]>([])
const loading = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const loadActuators = async () => {
  loading.value = true
  try {
    const res = await actuatorApi.list()
    const innerData = extractResponseData<{ count: number; items: ActuatorInfo[] }>(res)
    actuators.value = innerData?.items || []
  } catch (e) {
    console.error('Load actuators error:', e)
    actuators.value = []
  } finally {
    loading.value = false
  }
}

const getTypeLabel = (type: string) => {
  const typeMap: Record<string, string> = {
    web_ui: 'Web UI',
    android_ui: 'Android UI',
    pytest: 'Pytest',
    pytest_web: 'Pytest Web',
  }
  return typeMap[type] || type
}

const getTypeTagColor = (type: string) => {
  const typeMap: Record<string, string> = {
    web_ui: 'arcoblue',
    android_ui: 'green',
    pytest: 'orangered',
    pytest_web: 'purple',
  }
  return typeMap[type] || 'gray'
}

const formatTime = (isoString: string) => {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString(isEnglish.value ? 'en-US' : 'zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const refresh = () => loadActuators()

defineExpose({ refresh })

onMounted(() => {
  loadActuators()
  // 每30秒刷新一次
  refreshTimer = setInterval(loadActuators, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped lang="scss">
.actuator-list {
  padding: 16px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .title {
    display: flex;
    align-items: center;
    gap: 12px;

    h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }

    .count {
      color: var(--color-text-3);
      font-size: 14px;
    }
  }
}

.mb-4 {
  margin-bottom: 16px;
}

.online-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #00b42a;
  box-shadow: 0 0 8px rgba(0, 180, 42, 0.5);
  display: inline-block;
}

.time-text {
  font-size: 12px;
  color: var(--color-text-3);
}
</style>
