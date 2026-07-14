<template>
  <a-modal
    v-model:visible="visible"
    :title="isEditing ? '编辑模板' : '新增模板'"
    :width="800"
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
      <a-form-item label="模板名称" field="name" :rules="[{ required: true, message: '请输入模板名称' }]">
        <a-input v-model="form.name" placeholder="如：失败通知模板" :max-length="100" />
      </a-form-item>

      <a-form-item label="描述" field="description">
        <a-input v-model="form.description" placeholder="可选描述" />
      </a-form-item>

      <VariableHintPanel @insert="onInsertVariable" />

      <a-form-item label="模板内容" field="content" :rules="[{ required: true, message: '请输入模板内容' }]">
        <div class="content-editor">
          <a-textarea
            ref="contentRef"
            v-model="form.content"
            placeholder="支持 Markdown 和 {{变量}} 占位符"
            :auto-size="{ minRows: 8, maxRows: 20 }"
            style="font-family: monospace;"
          />
        </div>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  createMessageTemplate,
  updateMessageTemplate,
  type MessageTemplate,
  type MessageTemplateFormData,
} from '../services/notificationService';
import VariableHintPanel from './VariableHintPanel.vue';

const visible = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref();
const contentRef = ref();

const defaultForm = (): MessageTemplateFormData => ({
  name: '',
  content: '',
  description: '',
});

const form = reactive<MessageTemplateFormData>(defaultForm());

const open = (tpl?: MessageTemplate) => {
  Object.assign(form, defaultForm());
  if (tpl) {
    isEditing.value = true;
    editingId.value = tpl.id;
    form.name = tpl.name;
    form.content = tpl.content;
    form.description = tpl.description || '';
  } else {
    isEditing.value = false;
    editingId.value = null;
  }
  visible.value = true;
};

const handleClose = () => {
  visible.value = false;
};

const onInsertVariable = (varName: string) => {
  const insertion = `{{${varName}}}`;
  const textarea = contentRef.value?.$el?.querySelector('textarea');
  if (textarea) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    form.content = form.content.substring(0, start) + insertion + form.content.substring(end);
    nextTick(() => {
      textarea.focus();
      const newPos = start + insertion.length;
      textarea.setSelectionRange(newPos, newPos);
    });
  } else {
    form.content += insertion;
  }
};

const handleSubmit = async () => {
  const errors = await formRef.value?.validate();
  if (errors) return;

  submitting.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await updateMessageTemplate(editingId.value, { ...form });
      Message.success('模板已更新');
    } else {
      await createMessageTemplate({ ...form });
      Message.success('模板已创建');
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

<style scoped>
.content-editor {
  width: 100%;
}
</style>
