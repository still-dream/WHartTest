<template>
  <div class="device-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.platform"
          placeholder="平台"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option value="android">Android</a-option>
          <a-option value="ios">iOS</a-option>
        </a-select>
        <a-select
          v-model="filters.connection_type"
          placeholder="连接类型"
          allow-clear
          style="width: 150px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option value="adb_tcp">ADB TCP 远程</a-option>
          <a-option value="emulator">Android 模拟器</a-option>
          <a-option value="cloud">云真机平台</a-option>
          <a-option value="usb">USB 直连</a-option>
        </a-select>
        <a-input-search
          v-model="filters.search"
          placeholder="搜索设备名称/序列号"
          allow-clear
          style="width: 240px"
          @search="onSearch"
          @clear="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          新增设备
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="deviceData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 1100 }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #connection_type="{ record }">
        <a-tag color="cyan">{{ connectionTypeLabels[record.connection_type as AppUiConnectionType] }}</a-tag>
      </template>
      <template #platform="{ record }">
        <a-tag :color="record.platform === 'android' ? 'green' : 'gray'">
          {{ record.platform === 'android' ? 'Android' : 'iOS' }}
        </a-tag>
      </template>
      <template #device_uri="{ record }">
        <a-tooltip :content="record.device_uri" position="top">
          <div class="ellipsis-text">{{ record.device_uri }}</div>
        </a-tooltip>
      </template>
      <template #status="{ record }">
        <a-badge
          :status="badgeStatus[record.status as AppUiDeviceStatus]"
          :text="deviceStatusLabels[record.status as AppUiDeviceStatus]"
        />
      </template>
      <template #is_default="{ record }">
        <a-tag v-if="record.is_default" color="green" size="small">默认</a-tag>
        <span v-else>-</span>
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" status="success" :loading="checkingId === record.id" @click="checkDevice(record)">
            <template #icon><icon-sync /></template>
            检测
          </a-button>
          <a-button type="text" size="mini" @click="editDevice(record)">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
          <a-popconfirm content="确定删除该设备？" @ok="deleteDevice(record)">
            <a-button type="text" size="mini" status="danger">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-table>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEdit ? '编辑设备' : '新增设备'"
      :ok-loading="submitting"
      :width="560"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item field="name" label="设备名称" required>
          <a-input v-model="formData.name" placeholder="如：测试机-小米12" :max-length="100" />
        </a-form-item>
        <a-form-item field="connection_type" label="连接类型" required>
          <a-select v-model="formData.connection_type" placeholder="请选择连接类型">
            <a-option value="adb_tcp">ADB TCP 远程</a-option>
            <a-option value="emulator">Android 模拟器</a-option>
            <a-option value="cloud">云真机平台</a-option>
            <a-option value="usb">USB 直连</a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="platform" label="平台" required>
          <a-radio-group v-model="formData.platform">
            <a-radio value="android">Android</a-radio>
            <a-radio value="ios">iOS</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item field="device_uri" label="设备连接 URI" required>
          <a-input v-model="formData.device_uri" :placeholder="deviceUriPlaceholder" />
        </a-form-item>
        <a-form-item field="device_serial" label="设备序列号">
          <a-input v-model="formData.device_serial" placeholder="可选，设备序列号" />
        </a-form-item>
        <a-form-item field="description" label="设备描述">
          <a-textarea v-model="formData.description" placeholder="请输入描述" :auto-size="{ minRows: 2 }" />
        </a-form-item>
        <a-form-item field="is_default" label="设为默认设备">
          <a-switch v-model="formData.is_default" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconSync } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { deviceApi } from '../api'
import type {
  AppUiDevice, AppUiDeviceForm, AppUiConnectionType, AppUiDeviceStatus,
} from '../types'
import { extractPaginationData } from '../types'

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const submitting = ref(false)
const deviceData = ref<AppUiDevice[]>([])
const modalVisible = ref(false)
const isEdit = ref(false)
const currentDevice = ref<AppUiDevice | null>(null)
const formRef = ref()
const checkingId = ref<number | null>(null)

const filters = reactive({
  platform: undefined as string | undefined,
  connection_type: undefined as string | undefined,
  search: '',
})
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const formData = reactive<AppUiDeviceForm>({
  project: 0,
  name: '',
  connection_type: 'adb_tcp',
  platform: 'android',
  device_uri: '',
  device_serial: '',
  status: 'offline',
  description: '',
  is_default: false,
})

const rules = {
  name: [{ required: true, message: '请输入设备名称' }],
  connection_type: [{ required: true, message: '请选择连接类型' }],
  platform: [{ required: true, message: '请选择平台' }],
  device_uri: [{ required: true, message: '请输入设备连接 URI' }],
}

const connectionTypeLabels: Record<AppUiConnectionType, string> = {
  adb_tcp: 'ADB TCP 远程',
  emulator: 'Android 模拟器',
  cloud: '云真机平台',
  usb: 'USB 直连',
}

const deviceUriPlaceholder = computed(() => {
  if (formData.platform === 'ios') {
    return 'ios:///127.0.0.1:8100'
  }
  switch (formData.connection_type) {
    case 'adb_tcp':
      return 'android://127.0.0.1:5037/安卓手机无线IP:5555'
    case 'emulator':
      return 'android://127.0.0.1:5037/127.0.0.1:62001'
    case 'cloud':
      return 'android://云平台IP:端口/设备ID'
    case 'usb':
      return 'android://127.0.0.1:5037/设备序列号'
    default:
      return 'android://127.0.0.1:5037/设备序列号'
  }
})

const deviceStatusLabels: Record<AppUiDeviceStatus, string> = {
  online: '在线',
  offline: '离线',
  busy: '忙碌',
}

const badgeStatus: Record<AppUiDeviceStatus, string> = {
  online: 'success',
  offline: 'default',
  busy: 'warning',
}

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '设备名称', dataIndex: 'name', ellipsis: true, tooltip: true, width: 150 },
  { title: '连接类型', slotName: 'connection_type', width: 130, align: 'center' as const },
  { title: '平台', slotName: 'platform', width: 90, align: 'center' as const },
  { title: '设备 URI', slotName: 'device_uri', width: 220 },
  { title: '状态', slotName: 'status', width: 100, align: 'center' as const },
  { title: '默认', slotName: 'is_default', width: 70, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 220, fixed: 'right' as const, align: 'center' as const },
]

const fetchDevices = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await deviceApi.list({
      project: projectId.value,
      platform: filters.platform,
      connection_type: filters.connection_type,
      search: filters.search || undefined,
    })
    const { items, count } = extractPaginationData(res)
    deviceData.value = items
    pagination.total = count
  } catch {
    Message.error('获取设备列表失败')
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchDevices()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchDevices()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchDevices()
}

const resetForm = () => {
  Object.assign(formData, {
    project: projectId.value || 0,
    name: '',
    connection_type: 'adb_tcp',
    platform: 'android',
    device_uri: '',
    device_serial: '',
    status: 'offline',
    description: '',
    is_default: false,
  })
  formRef.value?.clearValidate()
}

const showAddModal = () => {
  isEdit.value = false
  currentDevice.value = null
  resetForm()
  modalVisible.value = true
}

const editDevice = (record: AppUiDevice) => {
  isEdit.value = true
  currentDevice.value = record
  Object.assign(formData, {
    project: record.project,
    name: record.name,
    connection_type: record.connection_type,
    platform: record.platform,
    device_uri: record.device_uri,
    device_serial: record.device_serial,
    status: record.status,
    description: record.description || '',
    is_default: record.is_default,
  })
  modalVisible.value = true
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  try {
    await formRef.value?.validate()
  } catch {
    Message.warning('请填写必填项')
    done(false)
    return
  }
  submitting.value = true
  try {
    if (isEdit.value && currentDevice.value) {
      await deviceApi.update(currentDevice.value.id, formData)
      Message.success('更新成功')
    } else {
      await deviceApi.create(formData)
      Message.success('创建成功')
    }
    done(true)
    fetchDevices()
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('\n')
      Message.error({ content: messages, duration: 5000 })
    } else {
      Message.error(err?.error || (isEdit.value ? '更新失败' : '创建失败'))
    }
    done(false)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

const deleteDevice = async (record: AppUiDevice) => {
  try {
    await deviceApi.delete(record.id)
    Message.success('删除成功')
    fetchDevices()
  } catch {
    Message.error('删除失败')
  }
}

const checkDevice = async (record: AppUiDevice) => {
  checkingId.value = record.id
  try {
    const res = await deviceApi.check(record.id)
    const data = (res as any).data?.data ?? (res as any).data
    if (data?.status === 'online') {
      Message.success(data?.message || '设备连接成功')
    } else {
      Message.warning(data?.message || '设备连接失败')
    }
    fetchDevices()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || '设备检测失败')
  } finally {
    checkingId.value = null
  }
}

const refresh = () => fetchDevices()

defineExpose({ refresh })

watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchDevices()
  }
}, { immediate: true })
</script>

<style scoped>
.device-list {
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
.ellipsis-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
