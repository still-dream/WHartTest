## Task 9: Frontend MessageTemplate page + VariableHintPanel

**Files:**
- Create: `WHartTest_Vue/src/features/notifications/components/VariableHintPanel.vue`
- Create: `WHartTest_Vue/src/features/notifications/views/MessageTemplateView.vue`
- Create: `WHartTest_Vue/src/features/notifications/components/TemplateFormModal.vue`

**Interfaces:**
- Produces: VariableHintPanel (reusable), MessageTemplateView, TemplateFormModal
- Consumes: notificationService, NOTIFICATION_VARIABLES, Arco Design

- [ ] **Step 1: Create VariableHintPanel component**

Create `WHartTest_Vue/src/features/notifications/components/VariableHintPanel.vue`:

```vue
<template>
  <div class="variable-hint-panel">
    <a-collapse :default-active-key="[]">
      <a-collapse-item key="vars" header="变量参考">
        <div class="var-grid">
          <div
            v-for="v in variables"
            :key="v.name"
            class="var-item"
            @click="onVarClick(v)"
          >
            <a-tooltip :content="`点击插入 {{${v.name}}} - ${v.description}`">
              <a-tag color="arcoblue" style="cursor: pointer">
                {{ '{{' + v.name + '}}' }}
              </a-tag>
            </a-tooltip>
            <span class="var-desc">{{ v.description }}</span>
          </div>
        </div>
      </a-collapse-item>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { NOTIFICATION_VARIABLES, type NotificationVariable } from '../types';

const variables = NOTIFICATION_VARIABLES;

const emit = defineEmits<{
  (e: 'insert', varName: string): void;
}>();

const onVarClick = (v: NotificationVariable) => {
  emit('insert', v.name);
};
</script>

<style scoped>
.variable-hint-panel {
  margin-bottom: 8px;
}

.var-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.var-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.var-desc {
  font-size: 12px;
  color: var(--color-text-3);
}
</style>
```

- [ ] **Step 2: Create TemplateFormModal component**

Create `WHartTest_Vue/src/features/notifications/components/TemplateFormModal.vue`:

```vue
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
```

- [ ] **Step 3: Create MessageTemplateView page**

Create `WHartTest_Vue/src/features/notifications/views/MessageTemplateView.vue`:

```vue
<template>
  <div class="message-template-view">
    <a-card title="消息模板库">
      <template #extra>
        <a-button type="primary" @click="handleAdd">
          <template #icon><icon-plus /></template>
          新增模板
        </a-button>
      </template>

      <a-table
        :data="templateList"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @page-change="onPageChange"
      >
        <template #columns>
          <a-table-column title="模板名称" data-index="name" />
          <a-table-column title="平台类型" data-index="platform_type">
            <template #cell="{ record }">
              <a-tag color="blue">{{ record.platform_type }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="类型" data-index="is_system">
            <template #cell="{ record }">
              <a-tag :color="record.is_system ? 'orangered' : 'cyan'">
                {{ record.is_system ? '系统内置' : '用户创建' }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="描述" data-index="description" :ellipsis="true" />
          <a-table-column title="创建人" data-index="creator">
            <template #cell="{ record }">
              {{ record.creator_name || record.creator || '-' }}
            </template>
          </a-table-column>
          <a-table-column title="更新时间" data-index="updated_at">
            <template #cell="{ record }">
              {{ formatDate(record.updated_at) }}
            </template>
          </a-table-column>
          <a-table-column title="操作" :width="150">
            <template #cell="{ record }">
              <a-space>
                <a-button type="text" size="small" @click="handleEdit(record)">编辑</a-button>
                <a-popconfirm
                  v-if="!record.is_system"
                  content="确定删除该模板？"
                  @ok="handleDelete(record)"
                >
                  <a-button type="text" status="danger" size="small">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>

    <TemplateFormModal ref="formModal" @success="loadData" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconPlus } from '@arco-design/web-vue/es/icon';
import {
  getMessageTemplates,
  deleteMessageTemplate,
  type MessageTemplate,
} from '../services/notificationService';
import TemplateFormModal from '../components/TemplateFormModal.vue';

const loading = ref(false);
const templateList = ref<MessageTemplate[]>([]);
const formModal = ref<InstanceType<typeof TemplateFormModal>>();

const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
});

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString('zh-CN');
};

const loadData = async () => {
  loading.value = true;
  try {
    const data = await getMessageTemplates();
    templateList.value = data;
    pagination.value.total = templateList.value.length;
  } catch {
    templateList.value = [];
  } finally {
    loading.value = false;
  }
};

const onPageChange = (page: number) => {
  pagination.value.current = page;
};

const handleAdd = () => {
  formModal.value?.open();
};

const handleEdit = (record: MessageTemplate) => {
  formModal.value?.open(record);
};

const handleDelete = async (record: MessageTemplate) => {
  try {
    await deleteMessageTemplate(record.id);
    Message.success('删除成功');
    loadData();
  } catch {
    Message.error('删除失败');
  }
};

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.message-template-view {
  padding: 16px;
}
</style>
```

- [ ] **Step 4: Build to verify no errors**

```bash
cd WHartTest_Vue && npm run build
```

Expected: Build succeeds with no TypeScript errors in the new files.

- [ ] **Step 5: Commit**

```bash
cd WHartTest_Vue && git add src/features/notifications/ && git commit -m "feat: add message template page, template form modal, and variable hint panel"
```
