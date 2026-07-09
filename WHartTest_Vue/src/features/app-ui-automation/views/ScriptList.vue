<template>
  <div class="script-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.module"
          placeholder="选择模块"
          allow-clear
          style="width: 180px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
            {{ mod.name }}
          </a-option>
        </a-select>
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
        <a-input-search
          v-model="filters.search"
          placeholder="搜索脚本名称"
          allow-clear
          style="width: 220px"
          @search="onSearch"
          @clear="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          上传脚本
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="scriptData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 1100 }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #module_name="{ record }">
        <a-tag color="arcoblue">{{ record.module_name }}</a-tag>
      </template>
      <template #platform="{ record }">
        <a-tag :color="record.platform === 'android' ? 'green' : 'gray'">
          {{ record.platform === 'android' ? 'Android' : 'iOS' }}
        </a-tag>
      </template>
      <template #level="{ record }">
        <a-tag :color="levelColors[record.level as AppUiCaseLevel]">{{ record.level }}</a-tag>
      </template>
      <template #status="{ record }">
        <a-tag :color="statusColors[record.status as AppUiScriptStatus]">
          {{ statusLabels[record.status as AppUiScriptStatus] }}
        </a-tag>
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="previewScript(record)">
            <template #icon><icon-eye /></template>
            预览
          </a-button>
          <a-button type="text" size="mini" status="success" @click="showExecuteDialog(record)">
            <template #icon><icon-play-arrow /></template>
            执行
          </a-button>
          <a-button type="text" size="mini" @click="editScript(record)">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
          <a-popconfirm content="确定删除该脚本？关联的执行记录也会被删除。" @ok="deleteScript(record)">
            <a-button type="text" size="mini" status="danger">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-table>

    <!-- 上传/编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEdit ? '编辑脚本' : '上传脚本'"
      :ok-loading="submitting"
      :ok-text="uploadSuccess ? '关闭' : (isEdit ? '更新' : '上传')"
      :width="560"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item field="module" label="所属模块" required>
          <a-select v-model="formData.module" placeholder="请选择模块">
            <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
              {{ mod.name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="name" label="脚本名称" required>
          <a-input v-model="formData.name" placeholder="请输入脚本名称" :max-length="255" />
        </a-form-item>
        <a-form-item field="platform" label="目标平台" required>
          <a-radio-group v-model="formData.platform">
            <a-radio value="android">Android</a-radio>
            <a-radio value="ios">iOS</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item field="level" label="用例等级">
          <a-select v-model="formData.level" placeholder="请选择等级">
            <a-option value="P0">P0</a-option>
            <a-option value="P1">P1</a-option>
            <a-option value="P2">P2</a-option>
            <a-option value="P3">P3</a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="description" label="描述">
          <a-textarea v-model="formData.description" placeholder="请输入描述" :auto-size="{ minRows: 2 }" />
        </a-form-item>
        <a-form-item field="script_file" label="Airtest 脚本" :required="!isEdit">
          <div class="upload-buttons">
            <a-button type="primary" @click="triggerFileSelect">
              <template #icon><icon-upload /></template>
              选择文件 (.zip/.py)
            </a-button>
            <a-button :loading="zippingAir" @click="triggerAirDirSelect">
              <template #icon><icon-folder /></template>
              选择 .air 目录
            </a-button>
          </div>
          <input ref="fileInputRef" type="file" accept=".zip,.py" style="display:none" @change="onFileSelect" />
          <input ref="airDirInputRef" type="file" webkitdirectory style="display:none" @change="onAirDirChange" />
          <div v-if="selectedFileName" class="selected-file">
            <span class="selected-file-name">{{ selectedFileName }}</span>
            <a-button v-if="!uploadSuccess" type="text" size="mini" status="danger" @click="clearSelectedFile">
              <template #icon><icon-delete /></template>
            </a-button>
          </div>
          <div v-if="isEdit && currentScript?.script_file && !selectedFileName" class="file-hint">
            当前文件：{{ currentScript.script_file }}（重新上传将覆盖）
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 脚本预览弹窗 -->
    <a-modal v-model:visible="previewVisible" title="脚本预览" :width="720" :footer="false">
      <div v-if="previewLoading" style="text-align: center; padding: 40px">
        <a-spin />
      </div>
      <div v-else-if="previewData">
        <a-tag color="arcoblue" style="margin-bottom: 8px">入口: {{ previewData.entry }}</a-tag>
        <pre class="script-preview">{{ previewData.content }}</pre>
      </div>
      <a-empty v-else description="无内容" />
    </a-modal>

    <!-- 执行设备选择弹窗 -->
    <a-modal
      v-model:visible="executeVisible"
      title="执行脚本"
      :ok-loading="executing"
      @before-ok="handleExecute"
      @cancel="executeVisible = false"
    >
      <p v-if="currentScript" class="exec-hint">
        脚本：<b>{{ currentScript.name }}</b>
      </p>
      <a-form layout="vertical">
        <a-form-item label="选择设备">
          <a-select v-model="executeDeviceId" placeholder="请选择设备（可选）" allow-clear>
            <a-option v-for="dev in deviceOptions" :key="dev.id" :value="dev.id">
              {{ dev.name }} ({{ dev.platform }})
            </a-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconPlus, IconEdit, IconDelete, IconEye, IconUpload, IconPlayArrow, IconFolder,
} from '@arco-design/web-vue/es/icon'
import JSZip from 'jszip'
import { useProjectStore } from '@/store/projectStore'
import { scriptApi, moduleApi, deviceApi } from '../api'
import type {
  AppUiScript, AppUiModule, AppUiDevice, AppUiCaseLevel, AppUiScriptStatus,
  AppUiScriptPreview,
} from '../types'
import { extractPaginationData, extractResponseData } from '../types'

const props = defineProps<{
  selectedModuleId?: number
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const submitting = ref(false)
const scriptData = ref<AppUiScript[]>([])
const moduleOptions = ref<AppUiModule[]>([])
const deviceOptions = ref<AppUiDevice[]>([])
const modalVisible = ref(false)
const previewVisible = ref(false)
const executeVisible = ref(false)
const isEdit = ref(false)
const currentScript = ref<AppUiScript | null>(null)
const formRef = ref()
const selectedFile = ref<File | null>(null)
const selectedFileName = ref('')
const fileInputRef = ref<HTMLInputElement>()
const airDirInputRef = ref<HTMLInputElement>()
const zippingAir = ref(false)
const uploadSuccess = ref(false)

const filters = reactive({
  module: undefined as number | undefined,
  platform: undefined as string | undefined,
  search: '',
})
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const formData = reactive({
  project: 0,
  module: undefined as unknown as number,
  name: '',
  platform: 'android' as 'android' | 'ios',
  level: 'P2' as AppUiCaseLevel,
  description: '',
})

const rules = {
  module: [{ required: true, message: '请选择模块' }],
  name: [{ required: true, message: '请输入脚本名称' }],
  platform: [{ required: true, message: '请选择平台' }],
}

const levelColors: Record<AppUiCaseLevel, string> = {
  P0: 'red',
  P1: 'orange',
  P2: 'arcoblue',
  P3: 'gray',
}

const statusColors: Record<AppUiScriptStatus, string> = {
  idle: 'gray',
  running: 'arcoblue',
  success: 'green',
  failed: 'red',
}

const statusLabels: Record<AppUiScriptStatus, string> = {
  idle: '空闲',
  running: '执行中',
  success: '成功',
  failed: '失败',
}

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '模块', slotName: 'module_name', width: 120, align: 'center' as const },
  { title: '脚本名称', dataIndex: 'name', ellipsis: true, tooltip: true, width: 200 },
  { title: '平台', slotName: 'platform', width: 90, align: 'center' as const },
  { title: '等级', slotName: 'level', width: 70, align: 'center' as const },
  { title: '状态', slotName: 'status', width: 90, align: 'center' as const },
  { title: '创建者', dataIndex: 'creator_name', width: 100, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 260, fixed: 'right' as const, align: 'center' as const },
]

const previewLoading = ref(false)
const previewData = ref<AppUiScriptPreview | null>(null)

const executeDeviceId = ref<number | undefined>(undefined)
const executing = ref(false)

const flattenModules = (modules: AppUiModule[], level = 0, visited = new Set<number>()): AppUiModule[] => {
  const result: AppUiModule[] = []
  for (const mod of modules) {
    if (visited.has(mod.id)) continue
    visited.add(mod.id)
    result.push({ ...mod, name: '\u00A0\u00A0'.repeat(level) + mod.name })
    if (mod.children?.length) {
      result.push(...flattenModules(mod.children, level + 1, visited))
    }
  }
  return result
}

const fetchModules = async () => {
  if (!projectId.value) return
  try {
    const res = await moduleApi.tree(projectId.value)
    const modules = extractResponseData<AppUiModule[]>(res) || []
    moduleOptions.value = flattenModules(modules)
  } catch {
    Message.error('获取模块列表失败')
  }
}

const fetchDevices = async () => {
  if (!projectId.value) return
  try {
    const res = await deviceApi.list({ project: projectId.value })
    const { items } = extractPaginationData(res)
    deviceOptions.value = items
  } catch {
    // 静默失败
  }
}

const fetchScripts = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await scriptApi.list({
      project: projectId.value,
      module: filters.module,
      platform: filters.platform,
      search: filters.search || undefined,
    })
    const { items, count } = extractPaginationData(res)
    scriptData.value = items
    pagination.total = count
  } catch {
    Message.error('获取脚本列表失败')
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchScripts()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchScripts()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchScripts()
}

const triggerFileSelect = () => {
  fileInputRef.value?.click()
}

const onFileSelect = (e: Event) => {
  const input = e.target as HTMLInputElement
  if (!input.files || !input.files.length) return
  selectedFile.value = input.files[0]
  selectedFileName.value = input.files[0].name
  uploadSuccess.value = false
  input.value = ''
}

const clearSelectedFile = () => {
  selectedFile.value = null
  selectedFileName.value = ''
}

const triggerAirDirSelect = () => {
  airDirInputRef.value?.click()
}

const onAirDirChange = async (e: Event) => {
  const input = e.target as HTMLInputElement
  if (!input.files || !input.files.length) return

  // 校验选中的是 .air 目录
  const firstFile = input.files[0]
  const dirName = firstFile.webkitRelativePath.split('/')[0]
  if (!dirName.endsWith('.air')) {
    Message.warning('请选择 .air 目录')
    input.value = ''
    return
  }

  zippingAir.value = true
  try {
    const zip = new JSZip()
    Array.from(input.files).forEach(file => {
      zip.file(file.webkitRelativePath, file)
    })
    const blob = await zip.generateAsync({ type: 'blob' })
    const zipFile = new File([blob], `${dirName}.zip`, { type: 'application/zip' })

    selectedFile.value = zipFile
    selectedFileName.value = `${dirName}.zip`
    uploadSuccess.value = false
    Message.success(`已打包 ${dirName} 目录`)
  } catch {
    Message.error('打包 .air 目录失败')
  } finally {
    zippingAir.value = false
    input.value = ''
  }
}

const resetForm = () => {
  Object.assign(formData, {
    project: projectId.value || 0,
    module: undefined,
    name: '',
    platform: 'android',
    level: 'P2',
    description: '',
  })
  selectedFile.value = null
  selectedFileName.value = ''
  uploadSuccess.value = false
  formRef.value?.clearValidate()
}

const showAddModal = async () => {
  isEdit.value = false
  currentScript.value = null
  resetForm()
  if (props.selectedModuleId) {
    formData.module = props.selectedModuleId
  }
  if (!moduleOptions.value.length) {
    await fetchModules()
  }
  modalVisible.value = true
}

const editScript = async (record: AppUiScript) => {
  isEdit.value = true
  currentScript.value = record
  Object.assign(formData, {
    project: record.project,
    module: record.module,
    name: record.name,
    platform: record.platform,
    level: record.level,
    description: record.description || '',
  })
  selectedFile.value = null
  selectedFileName.value = ''
  uploadSuccess.value = false
  if (!moduleOptions.value.length) {
    await fetchModules()
  }
  modalVisible.value = true
}

const buildFormData = (): FormData => {
  const fd = new FormData()
  fd.append('project', String(formData.project))
  fd.append('module', String(formData.module))
  fd.append('name', formData.name)
  fd.append('platform', formData.platform)
  fd.append('level', formData.level)
  if (formData.description) {
    fd.append('description', formData.description)
  }
  if (selectedFile.value) {
    fd.append('script_file', selectedFile.value)
  }
  return fd
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  // 已上传成功后，点击"关闭"直接关闭弹窗
  if (uploadSuccess.value) {
    done(true)
    return
  }

  try {
    await formRef.value?.validate()
  } catch {
    Message.warning('请填写必填项')
    done(false)
    return
  }
  if (!isEdit.value && !selectedFile.value) {
    Message.warning('请上传脚本文件')
    done(false)
    return
  }
  // 编辑时若未选择新文件，也允许提交（仅修改基本信息）
  submitting.value = true
  try {
    const fd = buildFormData()
    if (isEdit.value && currentScript.value) {
      await scriptApi.update(currentScript.value.id, fd)
      Message.success('更新成功，可点击关闭')
    } else {
      await scriptApi.create(fd)
      Message.success('上传成功，可点击关闭')
    }
    uploadSuccess.value = true
    done(false)  // 不自动关闭，用户手动点击关闭
    fetchScripts()
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('\n')
      Message.error({ content: messages, duration: 5000 })
    } else {
      Message.error(err?.error || (isEdit.value ? '更新失败' : '上传失败'))
    }
    done(false)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

const deleteScript = async (record: AppUiScript) => {
  try {
    await scriptApi.delete(record.id)
    Message.success('删除成功')
    fetchScripts()
  } catch {
    Message.error('删除失败')
  }
}

const previewScript = async (record: AppUiScript) => {
  previewVisible.value = true
  previewLoading.value = true
  previewData.value = null
  try {
    const res = await scriptApi.preview(record.id)
    previewData.value = extractResponseData<AppUiScriptPreview>(res) || null
  } catch {
    Message.error('脚本预览失败，可能未正确解析')
  } finally {
    previewLoading.value = false
  }
}

const showExecuteDialog = async (record: AppUiScript) => {
  currentScript.value = record
  executeDeviceId.value = undefined
  if (!deviceOptions.value.length) {
    await fetchDevices()
  }
  executeVisible.value = true
}

const handleExecute = async (done: (closed: boolean) => void) => {
  if (!currentScript.value) {
    done(false)
    return
  }
  executing.value = true
  try {
    await scriptApi.execute(currentScript.value.id, {
      device_id: executeDeviceId.value,
      trigger_type: 'debug',
    })
    Message.success('脚本已开始执行')
    done(true)
    fetchScripts()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || '执行失败')
    done(false)
  } finally {
    executing.value = false
  }
}

const refresh = () => fetchScripts()

defineExpose({ refresh })

watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchModules()
    fetchScripts()
  }
}, { immediate: true })

watch(() => props.selectedModuleId, (val) => {
  filters.module = val
  pagination.current = 1
  fetchScripts()
})
</script>

<style scoped>
.script-list {
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
.script-preview {
  background: var(--color-fill-2);
  padding: 12px;
  border-radius: 4px;
  overflow: auto;
  max-height: 480px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
.file-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}
.upload-buttons {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.selected-file {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 6px 12px;
  background: var(--color-fill-1);
  border-radius: 4px;
  font-size: 13px;
}
.selected-file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.exec-hint {
  margin-bottom: 12px;
}
</style>
