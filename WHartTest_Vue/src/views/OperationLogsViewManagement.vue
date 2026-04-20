<template>
  <div class="operation-logs-management">
    <div class="page-header">
      <div class="search-box">
        <a-space :size="12">
          <a-input-search
            v-model="searchKeyword"
            placeholder="搜索用户名/功能点"
            allow-clear
            style="width: 250px"
            @search="onSearch"
          />
          <a-select
            v-model="filterUser"
            placeholder="筛选用户"
            allow-clear
            style="width: 150px"
            @change="onFilterChange"
          >
            <a-option
              v-for="user in userList"
              :key="user.id"
              :value="user.id"
              :label="user.username"
            />
          </a-select>
          <a-select
            v-model="filterFeature"
            placeholder="筛选功能点"
            allow-clear
            style="width: 150px"
            @change="onFilterChange"
          >
            <a-option
              v-for="feature in featureList"
              :key="feature"
              :value="feature"
              :label="feature"
            />
          </a-select>
          <a-range-picker
            v-model="dateRange"
            style="width: 280px"
            @change="onDateRangeChange"
          />
        </a-space>
      </div>
      <div class="action-buttons">
        <a-space>
          <a-button @click="refreshLogs">
            <template #icon><icon-refresh /></template>
            刷新
          </a-button>
          <a-button
            v-if="authStore.user?.is_staff"
            type="primary"
            status="danger"
            @click="showClearLogsModal"
          >
            <template #icon><icon-delete /></template>
            清理日志
          </a-button>
        </a-space>
      </div>
    </div>

    <a-card class="stats-card">
      <a-row :gutter="16">
        <a-col :span="6">
          <a-statistic title="总访问次数" :value="statistics.total_count">
            <template #prefix><icon-eye /></template>
          </a-statistic>
        </a-col>
        <a-col :span="6">
          <a-statistic title="今日访问" :value="statistics.today_count">
            <template #prefix><icon-calendar /></template>
          </a-statistic>
        </a-col>
        <a-col :span="6">
          <a-statistic title="本周访问" :value="statistics.week_count">
            <template #prefix><icon-clock-circle /></template>
          </a-statistic>
        </a-col>
        <a-col :span="6">
          <a-statistic title="活跃用户" :value="statistics.active_users">
            <template #prefix><icon-user /></template>
          </a-statistic>
        </a-col>
      </a-row>
    </a-card>

    <a-table
      :columns="columns"
      :data="logData"
      :pagination="pagination"
      :loading="loading"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #feature="{ record }">
        <a-tag color="arcoblue">{{ record.feature }}</a-tag>
      </template>
      <template #created_at="{ record }">
        {{ formatDateTime(record.created_at) }}
      </template>
      <template #ip_address="{ record }">
        <a-tooltip :content="record.ip_address || '-'">
          <span>{{ record.ip_address || '-' }}</span>
        </a-tooltip>
      </template>
    </a-table>

    <a-modal
      v-model:visible="clearLogsModalVisible"
      title="清理操作日志"
      @cancel="clearLogsModalVisible = false"
      @before-ok="handleClearLogs"
      :mask-closable="false"
    >
      <a-form :model="clearLogsForm" layout="vertical">
        <a-form-item field="days" label="保留最近多少天的日志">
          <a-input-number
            v-model="clearLogsForm.days"
            :min="1"
            :max="365"
            :default-value="30"
            style="width: 100%"
          />
          <template #extra>
            <span style="color: var(--color-text-3); font-size: 12px;">
              默认保留最近30天的日志，超过此时间的日志将被删除
            </span>
          </template>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import {
  IconRefresh,
  IconDelete,
  IconEye,
  IconCalendar,
  IconClockCircle,
  IconUser
} from '@arco-design/web-vue/es/icon';
import { useAuthStore } from '@/store/authStore';
import { request } from '@/utils/request';

interface OperationLog {
  id: number;
  user: number;
  username: string;
  user_email: string;
  feature: string;
  path: string;
  method: string;
  ip_address: string;
  user_agent: string;
  created_at: string;
}

interface User {
  id: number;
  username: string;
}

const authStore = useAuthStore();

const loading = ref(false);
const logData = ref<OperationLog[]>([]);
const userList = ref<User[]>([]);
const featureList = ref<string[]>([]);
const searchKeyword = ref('');
const filterUser = ref<number | undefined>();
const filterFeature = ref<string | undefined>();
const dateRange = ref<[Date, Date] | undefined>();

const statistics = reactive({
  total_count: 0,
  today_count: 0,
  week_count: 0,
  month_count: 0,
  active_users: 0
});

const pagination = reactive({
  total: 0,
  current: 1,
  pageSize: 20,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100],
});

const clearLogsModalVisible = ref(false);
const clearLogsForm = reactive({
  days: 30
});

const columns = [
  {
    title: 'ID',
    dataIndex: 'id',
    width: 80,
  },
  {
    title: '用户名',
    dataIndex: 'username',
    width: 120,
  },
  {
    title: '功能点',
    dataIndex: 'feature',
    slotName: 'feature',
    width: 150,
  },
  {
    title: '访问路径',
    dataIndex: 'path',
    width: 200,
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '请求方法',
    dataIndex: 'method',
    width: 100,
  },
  {
    title: 'IP地址',
    dataIndex: 'ip_address',
    slotName: 'ip_address',
    width: 130,
  },
  {
    title: '访问时间',
    dataIndex: 'created_at',
    slotName: 'created_at',
    width: 180,
  },
];

const fetchLogs = async () => {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      page: pagination.current,
      page_size: pagination.pageSize,
    };

    if (searchKeyword.value) {
      params.search = searchKeyword.value;
    }

    if (filterUser.value) {
      params.user = filterUser.value;
    }

    if (filterFeature.value) {
      params.feature = filterFeature.value;
    }

    if (dateRange.value && dateRange.value.length === 2) {
      params.created_at_gte = dateRange.value[0].toISOString();
      params.created_at_lte = dateRange.value[1].toISOString();
    }

    const response = await request<{ data: OperationLog[]; total: number }>({
      url: '/accounts/operation-logs/',
      method: 'GET',
      params,
    });

    if (response.success && response.data) {
      logData.value = response.data;
      pagination.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取操作日志失败');
      logData.value = [];
      pagination.total = 0;
    }
  } catch (error) {
    console.error('获取操作日志出错:', error);
    Message.error('获取操作日志时发生错误');
    logData.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
};

const fetchStatistics = async () => {
  try {
    const response = await request<any>({
      url: '/accounts/operation-logs/statistics/',
      method: 'GET',
    });

    if (response.success && response.data) {
      Object.assign(statistics, response.data);
    }
  } catch (error) {
    console.error('获取统计数据出错:', error);
  }
};

const fetchUserList = async () => {
  try {
    const response = await request<{ data: User[] }>({
      url: '/accounts/users/',
      method: 'GET',
      params: { page_size: 1000 },
    });

    if (response.success && response.data) {
      userList.value = response.data;
    }
  } catch (error) {
    console.error('获取用户列表出错:', error);
  }
};

const fetchFeatureList = async () => {
  try {
    const response = await request<{ data: OperationLog[] }>({
      url: '/accounts/operation-logs/',
      method: 'GET',
      params: { page_size: 1000 },
    });

    if (response.success && response.data) {
      const features = new Set(response.data.map(log => log.feature));
      featureList.value = Array.from(features).sort();
    }
  } catch (error) {
    console.error('获取功能点列表出错:', error);
  }
};

const onSearch = () => {
  pagination.current = 1;
  fetchLogs();
};

const onFilterChange = () => {
  pagination.current = 1;
  fetchLogs();
};

const onDateRangeChange = () => {
  pagination.current = 1;
  fetchLogs();
};

const onPageChange = (page: number) => {
  pagination.current = page;
  fetchLogs();
};

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1;
  fetchLogs();
};

const refreshLogs = () => {
  fetchLogs();
  fetchStatistics();
};

const showClearLogsModal = () => {
  clearLogsModalVisible.value = true;
};

const handleClearLogs = async () => {
  try {
    const response = await request<any>({
      url: '/accounts/operation-logs/clear_old_logs/',
      method: 'DELETE',
      params: { days: clearLogsForm.days },
    });

    if (response.success) {
      Message.success(response.message || '清理日志成功');
      clearLogsModalVisible.value = false;
      refreshLogs();
    } else {
      Message.error(response.error || '清理日志失败');
    }
  } catch (error) {
    console.error('清理日志出错:', error);
    Message.error('清理日志时发生错误');
  }
};

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-';
  const date = new Date(dateTime);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
};

onMounted(() => {
  fetchLogs();
  fetchStatistics();
  fetchUserList();
  fetchFeatureList();
});
</script>

<style scoped>
.operation-logs-management {
  padding: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.search-box {
  flex: 1;
}

.action-buttons {
  margin-left: 16px;
}

.stats-card {
  margin-bottom: 16px;
}
</style>
