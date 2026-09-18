<template>
  <div class="operation-log-management">
    <div class="page-header">
      <h2 class="page-title">操作日志</h2>
      <div class="action-buttons">
        <a-button @click="resetFilters">重置</a-button>
        <a-button type="primary" @click="reload">查询</a-button>
        <a-button
          v-if="isSuperuser"
          type="outline"
          status="danger"
          @click="onClearOldLogs"
        >
          清理旧日志
        </a-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <a-row :gutter="16" class="stats-row" v-if="statistics">
      <a-col :span="6">
        <a-statistic title="总访问次数" :value="statistics.total_count" />
      </a-col>
      <a-col :span="6">
        <a-statistic title="今日访问" :value="statistics.today_count" />
      </a-col>
      <a-col :span="6">
        <a-statistic title="本周访问" :value="statistics.week_count" />
      </a-col>
      <a-col :span="6">
        <a-statistic title="活跃用户数" :value="statistics.active_users" />
      </a-col>
    </a-row>

    <!-- 筛选区 -->
    <a-form :model="filters" layout="inline" class="filter-form">
      <a-form-item field="username" label="用户">
        <a-input
          v-model="filters.username"
          placeholder="按用户名筛选"
          allow-clear
          style="width: 160px"
        />
      </a-form-item>
      <a-form-item field="user" label="用户ID">
        <a-input
          v-model="filters.user"
          placeholder="用户ID"
          allow-clear
          style="width: 140px"
        />
      </a-form-item>
      <a-form-item field="feature" label="功能点">
        <a-select
          v-model="filters.feature"
          placeholder="按功能点筛选"
          allow-clear
          style="width: 180px"
        >
          <a-option
            v-for="opt in featureOptions"
            :key="opt"
            :value="opt"
          >{{ opt }}</a-option>
        </a-select>
      </a-form-item>
      <a-form-item field="search" label="关键词">
        <a-input
          v-model="filters.search"
          placeholder="搜索 用户名/功能点/路径"
          allow-clear
          style="width: 220px"
        />
      </a-form-item>
      <a-form-item field="dateRange" label="日期范围">
        <a-range-picker
          v-model="filters.dateRange"
          show-time
          format="YYYY-MM-DD HH:mm:ss"
          value-format="YYYY-MM-DD HH:mm:ss"
          style="width: 360px"
        />
      </a-form-item>
    </a-form>

    <!-- 表格 -->
    <a-table
      :columns="columns"
      :data="tableData"
      :pagination="pagination"
      :loading="loading"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #method="{ record }">
        <a-tag :color="methodColor(record.method)">{{ record.method }}</a-tag>
      </template>
      <template #created_at="{ record }">
        {{ formatDateTime(record.created_at) }}
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { operationLogService, type OperationLog, type OperationLogStatistics } from '@/services/operationLogService';
import { useAuthStore } from '@/store/authStore';

// 功能点下拉选项（与后端 middleware._extract_feature 中的 feature_mapping 保持一致）
const featureOptions = [
  '项目管理',
  '需求管理',
  '用例管理',
  '测试套件',
  '执行历史',
  'UI脚本库',
  '脚本执行',
  '知识库管理',
  'LLM对话',
  '智能编排',
  '提示词管理',
  '用户管理',
  '组织管理',
  '权限管理',
  'LLM配置',
  'KEY管理',
  'MCP配置',
  'Skills管理',
  '操作日志',
  'API访问',
];

// 筛选条件
const filters = reactive({
  username: '' as string | undefined,
  user: '' as string | undefined,
  feature: '' as string | undefined,
  search: '' as string | undefined,
  dateRange: [] as string[],
});

const tableData = ref<OperationLog[]>([]);
const loading = ref(false);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const statistics = ref<OperationLogStatistics | null>(null);

const authStore = useAuthStore();
const isSuperuser = computed(() => !!authStore.user?.is_superuser);

const columns = [
  { title: '时间', dataIndex: 'created_at', slotName: 'created_at', width: 170 },
  { title: '用户', dataIndex: 'username', width: 140 },
  { title: '功能点', dataIndex: 'feature', width: 140 },
  { title: '方法', dataIndex: 'method', slotName: 'method', width: 80 },
  { title: '路径', dataIndex: 'path', ellipsis: true },
  { title: 'IP', dataIndex: 'ip_address', width: 130 },
];

// Arco 表格的分页对象必须是 ref/reactive 或 getter；显式列出翻页按钮与页码跳转
const pagination = computed(() => ({
  current: currentPage.value,
  pageSize: pageSize.value,
  total: total.value,
  showPageSize: true,
  showTotal: true,
  showJumper: true,
  sizeCanChange: true,
  pageSizeOptions: [10, 20, 50, 100],
  defaultPageSize: 20,
  simple: false,
}));

function methodColor(method?: string) {
  switch ((method || '').toUpperCase()) {
    case 'GET': return 'arcoblue';
    case 'POST': return 'green';
    case 'PUT':
    case 'PATCH': return 'orange';
    case 'DELETE': return 'red';
    default: return 'gray';
  }
}

function formatDateTime(s: string) {
  if (!s) return '';
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function buildParams() {
  const params: Record<string, any> = {
    page: currentPage.value,
    page_size: pageSize.value,
    ordering: '-created_at',
  };
  if (filters.username) params.username = filters.username;
  if (filters.user) params.user = filters.user;
  if (filters.feature) params.feature = filters.feature;
  if (filters.search) params.search = filters.search;
  if (filters.dateRange && filters.dateRange.length === 2 && filters.dateRange[0] && filters.dateRange[1]) {
    // 显式扩展为 YYYY-MM-DD HH:mm:ss，Django 可直接解析。
    // 末日扩展到 23:59:59.999999，否则同一天选到晚上 8 点之后的数据会被排除。
    const start = filters.dateRange[0];
    const end = filters.dateRange[1];
    params.created_at__gte = start;
    params.created_at__lte = end.includes('00:00:00') && end.length === 10
      ? `${end} 23:59:59.999999`
      : end;
  }
  return params;
}

async function fetchList() {
  loading.value = true;
  try {
    const res = await operationLogService.list(buildParams() as any);
    if (res.success) {
      tableData.value = (res.data as any) || [];
      total.value = res.total ?? tableData.value.length;
    } else {
      Message.error(res.error || '加载操作日志失败');
    }
  } finally {
      loading.value = false;
  }
}

async function fetchStatistics() {
  const res = await operationLogService.statistics();
  if (res.success) statistics.value = res.data || null;
}

function reload() {
  currentPage.value = 1;
  fetchList();
}

function resetFilters() {
  filters.username = '';
  filters.user = '';
  filters.feature = '';
  filters.search = '';
  filters.dateRange = [];
  reload();
}

function onPageChange(p: number) {
  currentPage.value = p;
  fetchList();
}

function onPageSizeChange(s: number) {
  pageSize.value = s;
  currentPage.value = 1;
  fetchList();
}

function onClearOldLogs() {
  Modal.confirm({
    title: '清理旧日志',
    content: '将删除 30 天前的所有操作日志，是否继续？',
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      const res = await operationLogService.clearOldLogs(30);
      if (res.success) {
        Message.success(res.data?.message || '清理完成');
        reload();
        fetchStatistics();
      } else {
        Message.error(res.error || '清理失败');
      }
    },
  });
}

onMounted(() => {
  fetchList();
  fetchStatistics();
});
</script>

<style scoped>
.operation-log-management {
  /* 占满外层 .content 高度；min-height: 0 让 flex item 不被内部内容撑高，
     配合 MainLayout.content 的 overflow-y: auto 出滚动条 */
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
  background-color: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.15);
  overflow-y: auto;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
}
.action-buttons {
  display: flex;
  gap: 8px;
}
.stats-row {
  margin-bottom: 16px;
}
.filter-form {
  margin-bottom: 16px;
  row-gap: 12px;
}
</style>
