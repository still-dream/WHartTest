<template>
  <div class="app-package-list">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <div class="search-box">
        <a-input-search
          v-model="filters.search"
          placeholder="搜索包名 / 应用名"
          allow-clear
          style="width: 280px"
          @search="onSearch"
          @clear="onSearch"
        />
        <a-select
          v-model="filters.platform"
          placeholder="平台"
          allow-clear
          style="width: 120px; margin-left: 12px"
          @change="onSearch"
        >
          <a-option value="android">Android</a-option>
          <a-option value="ios">iOS</a-option>
        </a-select>
      </div>
      <div class="action-buttons">
        <!-- ★ 清理预览按钮：核心交互入口 -->
        <a-button @click="showCleanupPreview">
          <template #icon><icon-clock-circle /></template>
          清理预览
          <a-badge
            v-if="cleanupStats.pending > 0"
            :count="cleanupStats.pending"
            :max-count="99"
            :style="{ marginLeft: '4px' }"
          />
        </a-button>
        <a-button type="primary" @click="showCreateModal" style="margin-left: 8px;">
          <template #icon><icon-plus /></template>
          新建 APP
        </a-button>
      </div>
    </div>

    <!-- ★ 顶部 30 天自动清理全局提示 -->
    <a-alert
      v-if="cleanupStats.retention_days"
      type="info"
      show-icon
      :style="{ marginBottom: '16px' }"
    >
      <template #title>
        <span>
          APK 自动清理策略：上传超过
          <b>{{ cleanupStats.retention_days }} 天</b>
          且未受保护的版本将自动删除磁盘文件
        </span>
      </template>
      <template #default>
        <a-space size="large" style="font-size: 13px;">
          <span>每日 03:00 执行</span>
          <span>下次清理：<b>{{ formatDate(cleanupStats.next_run_at) }}</b></span>
          <span v-if="cleanupStats.last_run_at">
            上次清理：<b>{{ formatDate(cleanupStats.last_run_at) }}</b>
          </span>
          <a-link @click="showCleanupPreview">查看待清理列表 →</a-link>
        </a-space>
      </template>
    </a-alert>

    <!-- APP 列表 -->
    <a-table
      :columns="columns"
      :data="appList"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 1100 }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #app_name="{ record }">
        <a-space>
          <img
            v-if="record.icon"
            :src="record.icon"
            :alt="record.app_name"
            style="width: 32px; height: 32px; border-radius: 6px;"
          />
          <a-avatar v-else shape="square" :size="32">
            <icon-mobile />
          </a-avatar>
          <a-space direction="vertical" size="mini">
            <span style="font-weight: 500;">{{ record.app_name || record.package_name }}</span>
            <span style="font-size: 12px; color: var(--color-text-3);">{{ record.package_name }}</span>
          </a-space>
        </a-space>
      </template>

      <template #latest_version="{ record }">
        <template v-if="record.latest_version">
          <a-tag color="arcoblue">v{{ record.latest_version.version_name }}</a-tag>
          <a-tag
            v-if="record.latest_version.days_to_expire !== null && !record.latest_version.is_protected"
            :color="expireColor(record.latest_version.days_to_expire)"
            size="small"
            style="margin-left: 4px;"
          >
            {{ expireText(record.latest_version.days_to_expire) }}
          </a-tag>
          <a-tag
            v-else-if="record.latest_version.is_protected"
            color="green"
            size="small"
            style="margin-left: 4px;"
          >
            <template #icon><icon-lock /></template>
            受保护
          </a-tag>
        </template>
        <span v-else style="color: var(--color-text-3);">-</span>
      </template>

      <template #total_versions="{ record }">
        <a-link @click="openVersions(record)">{{ record.total_versions }} 个版本</a-link>
      </template>

      <template #creator_name="{ record }">
        <span>{{ record.creator_name || '-' }}</span>
      </template>

      <template #created_at="{ record }">
        <span>{{ formatDate(record.created_at) }}</span>
      </template>

      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" status="success" @click="showUploadModal(record)">
            <template #icon><icon-upload /></template>
            上传版本
          </a-button>
          <a-button type="text" size="mini" @click="openVersions(record)">
            <template #icon><icon-list /></template>
            版本管理
          </a-button>
          <a-button type="text" size="mini" status="danger" @click="deleteApp(record)">
            <template #icon><icon-delete /></template>
            删除
          </a-button>
        </a-space>
      </template>
    </a-table>

    <!-- 新建 APP 弹窗 -->
    <a-modal
      v-model:visible="createModal.visible"
      title="新建 APP"
      :ok-loading="createModal.loading"
      @ok="handleCreate"
      @cancel="resetCreateForm"
    >
      <a-form :model="createModal.form" layout="vertical">
        <a-form-item field="package_name" label="包名" :rules="[{ required: true, message: '请输入包名' }]">
          <a-input v-model="createModal.form.package_name" placeholder="如：com.example.app" />
        </a-form-item>
        <a-form-item field="app_name" label="应用名称">
          <a-input v-model="createModal.form.app_name" placeholder="如：示例应用" />
        </a-form-item>
        <a-form-item field="description" label="描述">
          <a-textarea v-model="createModal.form.description" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 上传 APK 弹窗（带 30 天清理提示） -->
    <AppPackageUploadModal
      v-model:visible="uploadModal.visible"
      :package-data="uploadModal.package"
      @success="onUploadSuccess"
      @preview-cleanup="showCleanupPreview"
    />

    <!-- 清理预览弹窗 -->
    <AppCleanupPreviewModal
      v-model:visible="cleanupModal.visible"
      @cleaned="onCleaned"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import AppPackageUploadModal from './AppPackageUploadModal.vue'
import AppCleanupPreviewModal from './AppCleanupPreviewModal.vue'
import { appPackageApi } from '../api'
import type { AppPackage, AppPackageVersion, PaginatedResponse } from '../types'
import { extractPaginationData } from '../types'

// ============ 筛选与分页 ============
const filters = ref({
  search: '',
  platform: '',
})
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
})
const loading = ref(false)
const appList = ref<AppPackage[]>([])

// ============ 清理统计 ============
const cleanupStats = ref({
  retention_days: 30,
  pending: 0,
  next_run_at: null as string | null,
  last_run_at: null as string | null,
})

// ============ 弹窗状态 ============
const createModal = reactive({
  visible: false,
  loading: false,
  form: { package_name: '', app_name: '', description: '' },
})

const uploadModal = reactive({
  visible: false,
  package: null as AppPackage | null,
})

const cleanupModal = reactive({
  visible: false,
})

const columns = [
  { title: '应用', slotName: 'app_name', width: 280 },
  { title: '最新版本', slotName: 'latest_version', width: 200 },
  { title: '版本数', slotName: 'total_versions', width: 100 },
  { title: '上传人', slotName: 'creator_name', width: 100 },
  { title: '创建时间', slotName: 'created_at', width: 160 },
  { title: '操作', slotName: 'operations', width: 280, fixed: 'right' },
]

// ============ 列表加载 ============
async function loadList() {
  loading.value = true
  try {
    const res: any = await appPackageApi.list({
      search: filters.value.search || undefined,
      platform: filters.value.platform || undefined,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    const { items, count } = extractPaginationData(res)
    appList.value = items as AppPackage[]
    pagination.total = count
  } catch (e: any) {
    Message.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadCleanupConfig() {
  try {
    const res: any = await appPackageApi.getCleanupConfig()
    cleanupStats.value = {
      retention_days: res?.retention_days || 30,
      pending: res?.total_cleaned || 0,
      next_run_at: res?.next_run_at || null,
      last_run_at: res?.last_run_at || null,
    }
  } catch (e) {
    // 静默
  }
}

function onSearch() {
  pagination.current = 1
  loadList()
}

function onPageChange(page: number) {
  pagination.current = page
  loadList()
}

function onPageSizeChange(size: number) {
  pagination.pageSize = size
  pagination.current = 1
  loadList()
}

// ============ 新建 APP ============
function showCreateModal() {
  createModal.visible = true
}

function resetCreateForm() {
  createModal.form = { package_name: '', app_name: '', description: '' }
}

async function handleCreate() {
  if (!createModal.form.package_name) {
    Message.error('请输入包名')
    return
  }
  createModal.loading = true
  try {
    await appPackageApi.create(createModal.form as any)
    Message.success('创建成功，请上传 APK')
    createModal.visible = false
    resetCreateForm()
    loadList()
  } catch (e: any) {
    Message.error(e?.message || '创建失败')
  } finally {
    createModal.loading = false
  }
}

// ============ 上传 APK ============
function showUploadModal(pkg: AppPackage) {
  uploadModal.package = pkg
  uploadModal.visible = true
}

function onUploadSuccess(version: AppPackageVersion) {
  loadList()
  loadCleanupConfig()
}

// ============ 删除 APP ============
function deleteApp(pkg: AppPackage) {
  Modal.confirm({
    title: '确认删除 APP？',
    content: `将删除「${pkg.app_name || pkg.package_name}」及其所有版本（包含所有 APK 文件），不可恢复！`,
    okText: '确认删除',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      try {
        await appPackageApi.delete(pkg.id)
        Message.success('删除成功')
        loadList()
      } catch (e: any) {
        Message.error(e?.message || '删除失败')
      }
    },
  })
}

// ============ 版本管理（占位） ============
function openVersions(pkg: AppPackage) {
  Message.info(`版本管理功能开发中。APP: ${pkg.package_name}`)
}

// ============ 清理预览 ============
function showCleanupPreview() {
  cleanupModal.visible = true
}

function onCleaned() {
  loadList()
  loadCleanupConfig()
}

// ============ 工具方法 ============
function formatDate(d: string | null | undefined): string {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function expireColor(days: number | null | undefined): string {
  if (days === null || days === undefined) return 'gray'
  if (days <= 0) return 'red'
  if (days <= 7) return 'orange'
  if (days <= 15) return 'gold'
  return 'green'
}

function expireText(days: number | null | undefined): string {
  if (days === null || days === undefined) return ''
  if (days <= 0) return `已过期 ${-days} 天`
  return `剩 ${days} 天`
}

onMounted(() => {
  loadList()
  loadCleanupConfig()
})

// 暴露给父组件 tab 切换时调用
defineExpose({
  refresh: loadList,
})
</script>

<style scoped>
.app-package-list {
  padding: 0;
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
.action-buttons {
  display: flex;
  align-items: center;
}
</style>
