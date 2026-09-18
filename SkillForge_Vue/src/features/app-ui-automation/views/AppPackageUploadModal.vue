<template>
  <a-modal
    :visible="visible"
    :title="title"
    :width="640"
    :ok-loading="uploading"
    :ok-button-props="{ disabled: !canSubmit }"
    :cancel-button-props="{ disabled: uploading }"
    @ok="handleSubmit"
    @cancel="handleCancel"
    @before-open="handleBeforeOpen"
    unmount-on-close
  >
    <!-- ★ 30 天自动清理提示（功能点核心 UI） -->
    <a-alert
      v-if="!hideRetentionNotice"
      type="warning"
      show-icon
      :style="{ marginBottom: '16px' }"
    >
      <template #title>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span>APK 文件将自动清理</span>
          <a-tag color="orange" size="small">{{ retentionDays }} 天后</a-tag>
        </div>
      </template>
      <div style="font-size: 13px; line-height: 1.6;">
        上传的 APK 文件将在
        <b>{{ retentionDays }} 天</b>
        后被系统自动清理（仅删除磁盘文件，数据库记录保留用于审计）。
        <br />
        - 清理时间：每天凌晨 <b>03:00</b>
        <br />
        - 重要版本请勾选下方「<b>受保护</b>」选项，<b>不会</b>被自动清理
        <br />
        - 清理前可通过 APP 列表的「清理预览」查看待清理列表
        <a-link @click="showCleanupPreview" style="margin-left: 4px">
          立即预览待清理列表 →
        </a-link>
      </div>
    </a-alert>

    <a-form :model="form" layout="vertical">
      <a-form-item
        field="apk_file"
        label="APK 文件"
        :rules="[{ required: true, message: '请选择 APK 文件' }]"
      >
        <a-upload
          :file-list="fileList"
          :auto-upload="false"
          :limit="1"
          :accept="'.apk'"
          :before-upload="beforeUpload"
          tip="支持 .apk 格式，单文件最大 500MB"
          @change="handleFileChange"
          @remove="handleFileRemove"
        >
          <template #upload-button>
            <a-button type="primary">
              <template #icon><icon-upload /></template>
              选择 APK 文件
            </a-button>
          </template>
        </a-upload>
      </a-form-item>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item
            field="version_name"
            label="版本号"
            :rules="[{ required: true, message: '请输入版本号' }]"
          >
            <a-input
              v-model="form.version_name"
              placeholder="如：1.2.3"
              allow-clear
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item
            field="version_code"
            label="版本代码"
            :rules="[{ required: true, message: '请输入版本代码' }]"
          >
            <a-input-number
              v-model="form.version_code"
              :min="1"
              :max="2147483647"
              placeholder="如：123"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item label="版本说明" field="changelog">
        <a-textarea
          v-model="form.changelog"
          :rows="3"
          :max-length="500"
          show-word-limit
          placeholder="本次更新内容..."
        />
      </a-form-item>

      <a-form-item label="状态" field="status">
        <a-radio-group v-model="form.status">
          <a-radio value="released">已发布</a-radio>
          <a-radio value="prerelease">预发布</a-radio>
          <a-radio value="draft">草稿</a-radio>
        </a-radio-group>
      </a-form-item>

      <!-- ★ 受保护开关：核心交互点 -->
      <a-form-item label="保留策略" field="is_protected">
        <a-card
          :bordered="true"
          :body-style="{ padding: '12px 16px' }"
          :style="form.is_protected ? { borderColor: '#00b42a', background: '#f6ffed' } : {}"
        >
          <a-space direction="vertical" size="small" style="width: 100%;">
            <a-switch
              v-model="form.is_protected"
              checked-text="受保护"
              unchecked-text="自动清理"
              @change="onProtectedChange"
            />
            <div style="font-size: 12px; color: var(--color-text-3); line-height: 1.5;">
              <span v-if="form.is_protected">
                ✅ <b style="color: #00b42a">此版本将被永久保留</b>，不会受 {{ retentionDays }} 天清理规则影响。
                建议用于：生产正式版、长期维护版本、合规基线。
              </span>
              <span v-else>
                ⏰ 此版本将在 <b>{{ expireDateText }}</b> ({{ retentionDays }} 天后) 被自动清理。
                建议用于：日常测试包、临时调试包。
              </span>
            </div>
          </a-space>
        </a-card>
      </a-form-item>
    </a-form>

    <template #footer>
      <a-button @click="handleCancel" :disabled="uploading">取消</a-button>
      <a-button type="primary" :loading="uploading" :disabled="!canSubmit" @click="handleSubmit">
        <template #icon><icon-upload /></template>
        {{ uploading ? '上传中...' : '开始上传' }}
      </a-button>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { appPackageApi } from '../api'
import type { AppPackage, AppPackageVersion, AppCleanupConfig } from '../types'

interface Props {
  visible: boolean
  packageData?: AppPackage | null
}

const props = withDefaults(defineProps<Props>(), {
  packageData: null,
})

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'success', version: AppPackageVersion): void
  (e: 'preview-cleanup'): void
}>()

// 默认 30 天，与后端 AppPackageVersion.RETENTION_DAYS 保持一致
const retentionDays = ref(30)
const hideRetentionNotice = ref(false)

const fileList = ref<any[]>([])
const uploading = ref(false)
const form = ref({
  version_name: '',
  version_code: 1,
  changelog: '',
  status: 'released' as 'released' | 'prerelease' | 'draft',
  is_protected: false,
})

const title = computed(() => {
  if (props.packageData) {
    return `上传新版本 - ${props.packageData.app_name || props.packageData.package_name}`
  }
  return '上传 APK'
})

const canSubmit = computed(() => {
  return fileList.value.length > 0
    && form.value.version_name
    && form.value.version_code
    && !uploading.value
})

const expireDateText = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + retentionDays.value)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
})

async function loadCleanupConfig() {
  try {
    const res: any = await appPackageApi.getCleanupConfig()
    if (res?.retention_days) {
      retentionDays.value = res.retention_days
    }
  } catch (e) {
    // 静默失败，使用默认值
  }
}

function handleBeforeOpen() {
  // 每次打开都重新加载配置，确保 retention_days 是最新的
  loadCleanupConfig()
  resetForm()
}

function resetForm() {
  fileList.value = []
  form.value = {
    version_name: '',
    version_code: 1,
    changelog: '',
    status: 'released',
    is_protected: false,
  }
}

function beforeUpload(file: File): boolean {
  if (!file.name.toLowerCase().endsWith('.apk')) {
    Message.error('只支持 .apk 格式')
    return false
  }
  if (file.size > 500 * 1024 * 1024) {
    Message.error('文件超过 500MB 限制')
    return false
  }
  return true
}

function handleFileChange(fileList_: any[]) {
  fileList.value = fileList_
  const file = fileList_[0]?.file
  if (file && !form.value.version_name) {
    // 尝试从文件名自动提取版本号
    const match = file.name.match(/[-_]?v?(\d+\.\d+\.\d+)/i)
    if (match) {
      form.value.version_name = match[1]
    }
  }
}

function handleFileRemove() {
  fileList.value = []
}

function onProtectedChange(val: boolean | string | number) {
  if (val) {
    Message.info('已设为受保护，不会被自动清理')
  } else {
    Message.info(`将在 ${retentionDays.value} 天后被自动清理`)
  }
}

function showCleanupPreview() {
  emit('preview-cleanup')
  // 关闭当前弹窗让用户看到清理预览
  emit('update:visible', false)
}

async function handleSubmit() {
  if (!canSubmit.value) return
  if (!props.packageData) {
    Message.error('请先选择 APP 包')
    return
  }

  const file = fileList.value[0]?.file
  if (!file) {
    Message.error('请选择 APK 文件')
    return
  }

  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('apk_file', file)
    fd.append('version_name', form.value.version_name)
    fd.append('version_code', String(form.value.version_code))
    fd.append('changelog', form.value.changelog)
    fd.append('status', form.value.status)
    fd.append('is_protected', form.value.is_protected ? 'true' : 'false')

    const res: any = await appPackageApi.uploadVersion(props.packageData.id, fd)
    Message.success(`版本 ${form.value.version_name} 上传成功`)
    emit('success', res)
    emit('update:visible', false)
  } catch (e: any) {
    Message.error(e?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

function handleCancel() {
  if (uploading.value) {
    Message.warning('上传中，请稍候')
    return
  }
  emit('update:visible', false)
}

watch(() => props.visible, (val) => {
  if (val) {
    loadCleanupConfig()
  }
})
</script>

<style scoped>
:deep(.arco-upload) {
  width: 100%;
}
</style>
