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
