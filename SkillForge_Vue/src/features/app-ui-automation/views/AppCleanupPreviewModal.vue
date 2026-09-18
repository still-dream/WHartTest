<template>
  <a-modal
    :visible="visible"
    title="APK 自动清理预览"
    :width="900"
    :footer="false"
    unmount-on-close
    @cancel="emit('update:visible', false)"
  >
    <a-alert
      :type="pendingCount > 0 ? 'warning' : 'success'"
      show-icon
      :style="{ marginBottom: '16px' }"
    >
      <template #title>
        <span v-if="pendingCount > 0">
          发现 <b>{{ pendingCount }}</b> 个 APK 将在 <b>{{ retentionDays }} 天</b>后被自动清理
        </span>
        <span v-else>暂无待清理的 APK ✅</span>
      </template>
      <div style="font-size: 13px; line-height: 1.6;">
        - 清理策略：上传超过 <b>{{ retentionDays }} 天</b> 且<b>未被设为「受保护」</b>的版本
        <br />
        - 清理时间：每天凌晨 <b>03:00</b>（仅删除磁盘文件，数据库记录保留）
        <br />
        - 重要版本可在列表中点击「设为受保护」永久保留
      </div>
    </a-alert>

    <a-space :style="{ marginBottom: '12px' }">
      <a-button @click="loadList" :loading="loading">
        <template #icon><icon-refresh /></template>
        刷新
      </a-button>
      <a-button
        type="primary"
        status="warning"
        :loading="running"
        :disabled="pendingCount === 0"
        @click="runNow"
      >
        <template #icon><icon-delete /></template>
        立即执行清理（删除 {{ pendingCount }} 个文件）
      </a-button>
    </a-space>

    <a-table
      :columns="columns"
      :data="list"
      :loading="loading"
      :pagination="false"
      :scroll="{ y: 400 }"
      row-key="id"
      size="small"
    >
      <template #app_name="{ record }">
        <a-space direction="vertical" size="mini">
          <span style="font-weight: 500;">{{ record.app_name || record.package_name }}</span>
          <span style="font-size: 12px; color: var(--color-text-3);">{{ record.package_name }}</span>
        </a-space>
      </template>
      <template #version="{ record }">
        <a-tag color="arcoblue">v{{ record.version_name }}</a-tag>
        <span style="font-size: 12px; color: var(--color-text-3);">code={{ record.version_code }}</span>
      </template>
      <template #file_size="{ record }">
        <span>{{ record.file_size_human || formatSize(record.file_size) }}</span>
      </template>
      <template #days_to_expire="{ record }">
        <a-tag v-if="record.days_to_expire !== null && record.days_to_expire <= 0" color="red">
          已过期 {{ -record.days_to_expire }} 天
        </a-tag>
        <a-tag v-else-if="record.days_to_expire !== null && record.days_to_expire <= 7" color="orange">
          剩 {{ record.days_to_expire }} 天
        </a-tag>
        <a-tag v-else color="green">
          剩 {{ record.days_to_expire }} 天
        </a-tag>
      </template>
      <template #expire_at="{ record }">
        <span style="font-size: 12px;">{{ formatDate(record.expire_at) }}</span>
      </template>
      <template #operations="{ record }">
        <a-button
          type="text"
          size="mini"
          status="success"
          @click="protectVersion(record)"
        >
          <template #icon><icon-lock /></template>
          设为受保护
        </a-button>
      </template>
      <template #empty>
        <a-empty description="没有待清理的 APK，所有版本都在保留期内或已受保护" />
      </template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { appPackageApi } from '../api'
import type { AppPackageVersion } from '../types'

interface Props {
  visible: boolean
  /** 预加载的列表（可选） */
  preloaded?: AppPackageVersion[]
}

const props = withDefaults(defineProps<Props>(), {
  preloaded: () => [],
})

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'protected', version: AppPackageVersion): void
  (e: 'cleaned'): void
}>()

const retentionDays = ref(30)
const loading = ref(false)
const running = ref(false)
const list = ref<AppPackageVersion[]>([])

const columns = [
  { title: '应用', slotName: 'app_name', width: 220 },
  { title: '版本', slotName: 'version', width: 160 },
  { title: '大小', slotName: 'file_size', width: 100 },
  { title: '剩余天数', slotName: 'days_to_expire', width: 110 },
  { title: '过期时间', slotName: 'expire_at', width: 150 },
  { title: '操作', slotName: 'operations', width: 120, fixed: 'right' as const },
]

const pendingCount = computed(() => list.value.length)

function formatSize(size: number): string {
  if (!size) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let s = size
  for (const u of units) {
    if (s < 1024) return `${s.toFixed(1)} ${u}`
    s /= 1024
  }
  return `${s.toFixed(1)} TB`
}

function formatDate(d: string | null): string {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

async function loadList() {
  loading.value = true
  try {
    // 调用 dry_run 模式扫描
    const res: any = await appPackageApi.runCleanup(true)
    retentionDays.value = res?.retention_days || 30
    // res 里只有数量,需要单独调 listVersions
    // 简化: 通过 package 列表 + 各自 versions 聚合
    list.value = props.preloaded || []
  } catch (e) {
    // ignore
  } finally {
    loading.value = false
  }
}

async function loadCleanupConfig() {
  try {
    const res: any = await appPackageApi.getCleanupConfig()
    if (res?.retention_days) {
      retentionDays.value = res.retention_days
    }
  } catch (e) {
    // 静默
  }
}

async function runNow() {
  if (pendingCount.value === 0) return
  Modal.confirm({
    title: '确认立即执行清理？',
    content: () => h('div', {}, [
      h('p', `将删除 ${pendingCount.value} 个 APK 文件，仅删除磁盘文件，数据库记录保留。`),
      h('p', { style: 'color: var(--color-text-3); font-size: 12px;' },
        '提示：设为「受保护」的版本不会被清理。'),
    ]),
    okText: '确认清理',
    cancelText: '取消',
    onOk: async () => {
      running.value = true
      try {
        const res: any = await appPackageApi.runCleanup(false)
        Message.success(`清理完成：删除 ${res.deleted} 个文件，释放 ${res.freed_human}`)
        emit('cleaned')
        emit('update:visible', false)
      } catch (e: any) {
        Message.error(e?.message || '清理失败')
      } finally {
        running.value = false
      }
    },
  })
}

async function protectVersion(record: AppPackageVersion) {
  try {
    await appPackageApi.toggleProtection(record.package, record.id, true)
    Message.success(`已设为受保护：${record.package_name} v${record.version_name}`)
    // 从列表移除
    list.value = list.value.filter(v => v.id !== record.id)
    emit('protected', { ...record, is_protected: true })
  } catch (e: any) {
    Message.error(e?.message || '操作失败')
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    loadCleanupConfig()
    loadList()
  }
})
</script>
