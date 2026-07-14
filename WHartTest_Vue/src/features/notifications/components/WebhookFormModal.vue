<template>
  <a-modal
    v-model:visible="visible"
    :title="isEditing ? '编辑推送地址' : '新增推送地址'"
    :width="520"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <template #footer>
      <a-space>
        <a-button @click="handleClose">取消</a-button>
        <a-button type="primary" :loading="submitting" @click="handleSubmit">保存</a-button>
      </a-space>
    </template>

    <a-form :model="form" layout="vertical" ref="formRef">
      <a-form-item label="地址名称" field="name" :rules="[{ required: true, message: '请输入地址名称' }]">
        <a-input v-model="form.name" placeholder="如：飞书测试群" :max-length="100" />
      </a-form-item>

      <a-form-item label="Webhook URL" field="url" :rules="[{ required: true, message: '请输入 Webhook URL' }]">
        <a-input v-model="form.url" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" />
      </a-form-item>

      <a-form-item label="描述" field="description">
        <a-textarea v-model="form.description" placeholder="可选描述" :auto-size="{ minRows: 2, maxRows: 4 }" />
      </a-form-item>

      <a-form-item label="启用状态" field="is_active">
        <a-switch v-model="form.is_active" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  createWebhookAddress,
  updateWebhookAddress,
  type WebhookAddress,
  type WebhookAddressFormData,
} from '../services/notificationService';

const visible = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref();

const defaultForm = (): WebhookAddressFormData => ({
  name: '',
  url: '',
  description: '',
  is_active: true,
});

const form = reactive<WebhookAddressFormData>(defaultForm());

const open = (addr?: WebhookAddress) => {
  Object.assign(form, defaultForm());
  if (addr) {
    isEditing.value = true;
    editingId.value = addr.id;
    form.name = addr.name;
    form.url = addr.url;
    form.description = addr.description || '';
    form.is_active = addr.is_active;
  } else {
    isEditing.value = false;
    editingId.value = null;
  }
  visible.value = true;
};

const handleClose = () => {
  visible.value = false;
};

const handleSubmit = async () => {
  const errors = await formRef.value?.validate();
  if (errors) return;

  submitting.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await updateWebhookAddress(editingId.value, { ...form });
      Message.success('推送地址已更新');
    } else {
      await createWebhookAddress({ ...form });
      Message.success('推送地址已创建');
    }
    visible.value = false;
    emit('success');
  } catch (error: any) {
    const msg = error?.response?.data?.detail || error?.error || '操作失败';
    Message.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  } finally {
    submitting.value = false;
  }
};

const emit = defineEmits<{ (e: 'success'): void }>();
defineExpose({ open });
</script>
