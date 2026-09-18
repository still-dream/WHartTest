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
