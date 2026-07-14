## Task 8: Frontend WebhookAddress management page

**Files:**
- Create: `WHartTest_Vue/src/features/notifications/views/WebhookAddressView.vue`
- Create: `WHartTest_Vue/src/features/notifications/components/WebhookFormModal.vue`

**Interfaces:**
- Produces: WebhookAddressView page, WebhookFormModal component
- Consumes: notificationService, Arco Design components

- [ ] **Step 1: Create WebhookFormModal component**

Create `WHartTest_Vue/src/features/notifications/components/WebhookFormModal.vue`:

```vue
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
```

- [ ] **Step 2: Create WebhookAddressView page**

Create `WHartTest_Vue/src/features/notifications/views/WebhookAddressView.vue`:

```vue
<template>
  <div class="webhook-address-view">
    <a-card title="推送地址管理">
      <template #extra>
        <a-button type="primary" @click="handleAdd">
          <template #icon><icon-plus /></template>
          新增地址
        </a-button>
      </template>

      <a-table
        :data="webhookList"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @page-change="onPageChange"
      >
        <template #columns>
          <a-table-column title="地址名称" data-index="name" />
          <a-table-column title="平台类型" data-index="platform_type">
            <template #cell="{ record }">
              <a-tag color="blue">{{ record.platform_type }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="URL" data-index="url">
            <template #cell="{ record }">
              <a-typography-text ellipsis style="max-width: 300px">
                {{ maskUrl(record.url) }}
              </a-typography-text>
            </template>
          </a-table-column>
          <a-table-column title="状态" data-index="is_active">
            <template #cell="{ record }">
              <a-tag :color="record.is_active ? 'green' : 'red'">
                {{ record.is_active ? '启用' : '停用' }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="描述" data-index="description" :ellipsis="true" />
          <a-table-column title="操作" :width="200">
            <template #cell="{ record }">
              <a-space>
                <a-button type="text" size="small" @click="handleEdit(record)">编辑</a-button>
                <a-button type="text" size="small" @click="handleTest(record)">测试推送</a-button>
                <a-popconfirm content="确定删除该地址？" @ok="handleDelete(record)">
                  <a-button type="text" status="danger" size="small">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>

    <WebhookFormModal ref="formModal" @success="loadData" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconPlus } from '@arco-design/web-vue/es/icon';
import {
  getWebhookAddresses,
  deleteWebhookAddress,
  testWebhookAddress,
  type WebhookAddress,
} from '../services/notificationService';
import WebhookFormModal from '../components/WebhookFormModal.vue';

const loading = ref(false);
const webhookList = ref<WebhookAddress[]>([]);
const formModal = ref<InstanceType<typeof WebhookFormModal>>();

const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
});

const maskUrl = (url: string) => {
  if (!url) return '';
  if (url.length <= 40) return url;
  return url.substring(0, 30) + '****' + url.substring(url.length - 10);
};

const loadData = async () => {
  loading.value = true;
  try {
    const data = await getWebhookAddresses();
    webhookList.value = data as WebhookAddress[];
    pagination.value.total = webhookList.value.length;
  } catch {
    webhookList.value = [];
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

const handleEdit = (record: WebhookAddress) => {
  formModal.value?.open(record);
};

const handleDelete = async (record: WebhookAddress) => {
  try {
    await deleteWebhookAddress(record.id);
    Message.success('删除成功');
    loadData();
  } catch {
    Message.error('删除失败');
  }
};

const handleTest = async (record: WebhookAddress) => {
  try {
    Message.loading('正在发送测试消息...');
    const result = await testWebhookAddress(record.id);
    Message.success(result.message || '测试消息已发送');
  } catch {
    Message.error('测试推送失败');
  }
};

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.webhook-address-view {
  padding: 16px;
}
</style>
```

- [ ] **Step 3: Build to verify no errors**

```bash
cd WHartTest_Vue && npm run build
```

Expected: Build succeeds with no TypeScript errors in the new files.

- [ ] **Step 4: Commit**

```bash
cd WHartTest_Vue && git add src/features/notifications/ && git commit -m "feat: add webhook address management page and form modal"
```
