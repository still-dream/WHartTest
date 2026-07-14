<template>
  <a-modal
    v-model:visible="visible"
    :title="modalTitle"
    :width="720"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <template #footer>
      <a-space>
        <a-button @click="handleClose">{{ modalText.cancel }}</a-button>
        <a-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ modalText.save }}
        </a-button>
      </a-space>
    </template>

    <div class="form-scroll-area">
      <a-form :model="form" layout="vertical" ref="formRef" size="small">
        <a-form-item :label="modalText.taskName" field="name" :rules="[{ required: true, message: modalText.enterTaskName }]">
          <a-input v-model="form.name" :placeholder="modalText.taskNamePlaceholder" :max-length="50" show-word-limit />
        </a-form-item>

        <a-form-item :label="modalText.taskDescription" field="description">
          <a-textarea v-model="form.description" :placeholder="modalText.taskDescriptionPlaceholder" :max-length="200" :auto-size="{ minRows: 2, maxRows: 3 }" />
        </a-form-item>

        <div class="form-row">
          <a-form-item :label="modalText.module" field="module" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-select v-model="form.module" :placeholder="modalText.selectModule" @change="onModuleChange">
              <a-option value="ui_automation">{{ modalText.uiAutomation }}</a-option>
              <a-option value="test_suite">{{ modalText.testSuite }}</a-option>
              <a-option value="app_ui_automation">APPUI 自动化</a-option>
            </a-select>
          </a-form-item>

          <a-form-item
            v-if="form.module === 'ui_automation'"
            :label="modalText.selectUiCase"
            field="ui_testcase_ids"
            :rules="[{ required: true, message: modalText.selectAtLeastOneUiCase }]"
          >
            <a-button type="outline" size="small" @click="openCaseSelectModal">
              <template #icon><icon-select-all /></template>
              {{ selectedUiCasesText }}
            </a-button>
          </a-form-item>

          <a-form-item
            v-if="form.module === 'test_suite'"
            :label="modalText.selectTestSuite"
            field="test_suite"
            :rules="[{ required: true, message: modalText.selectTestSuiteRequired }]"
          >
            <a-select
              v-model="form.test_suite"
              :placeholder="modalText.selectValue"
              :loading="loadingSuites"
              allow-search
              @popup-visible-change="(v: boolean) => v && loadTestSuites()"
            >
              <a-option v-for="suite in testSuites" :key="suite.id" :value="suite.id">{{ suite.name }}</a-option>
            </a-select>
          </a-form-item>

          <a-form-item
            v-if="form.module === 'app_ui_automation'"
            label="选择APPUI脚本"
            field="app_ui_scripts"
            :rules="[{ required: true, message: '请选择至少一个脚本' }]"
          >
            <a-button type="outline" size="small" @click="openAppUiScriptModal">
              <template #icon><icon-select-all /></template>
              {{ selectedAppUiScriptsText }}
            </a-button>
          </a-form-item>

          <a-form-item
            v-if="form.module === 'app_ui_automation'"
            label="执行设备"
            field="app_ui_device"
            :rules="[{ required: true, message: '请选择执行设备' }]"
          >
            <a-select
              v-model="form.app_ui_device"
              placeholder="请选择设备"
              :loading="loadingAppUiDevices"
              allow-search
              @popup-visible-change="(v: boolean) => v && loadAppUiDevices()"
            >
              <a-option v-for="dev in appUiDevices" :key="dev.id" :value="dev.id">
                {{ dev.name }} ({{ dev.platform }})
              </a-option>
            </a-select>
          </a-form-item>
        </div>

        <a-form-item
          v-if="form.module === 'api_automation'"
          :label="modalText.environment"
          field="environment"
          :rules="[{ required: true, message: modalText.selectEnvironmentRequired }]"
        >
          <a-select
            v-model="form.environment"
            :placeholder="modalText.selectEnvironment"
            :loading="loadingEnvironments"
            allow-search
            @popup-visible-change="(v: boolean) => v && loadEnvironments()"
          >
            <a-option v-for="env in environments" :key="env.id" :value="env.id">
              {{ env.name }} ({{ env.base_url }})
            </a-option>
          </a-select>
        </a-form-item>

        <a-form-item
          v-if="form.module === 'ui_automation' || form.module === 'test_suite'"
          :label="modalText.uiEnvironment"
          field="ui_environment"
          :rules="[{ required: true, message: modalText.selectUiEnvironmentRequired }]"
        >
          <a-select
            v-model="form.ui_environment"
            :placeholder="modalText.selectUiEnvironment"
            :loading="loadingUiEnvironments"
            allow-search
            @popup-visible-change="(v: boolean) => v && loadUiEnvironments()"
          >
            <a-option v-for="uiEnv in uiEnvironments" :key="uiEnv.id" :value="uiEnv.id">
              {{ uiEnv.name }} ({{ uiEnv.browser }})
            </a-option>
          </a-select>
        </a-form-item>

        <div v-if="form.module === 'ui_automation'" class="form-row-3">
          <a-form-item
            :label="modalText.actuator"
            field="actuator_id"
            :rules="[{ required: true, message: modalText.selectActuatorRequired }]"
          >
            <a-select
              v-model="form.actuator_id"
              :placeholder="modalText.selectActuator"
              :loading="loadingActuators"
              allow-search
              @popup-visible-change="(v: boolean) => v && loadActuators()"
            >
              <a-option v-for="actuator in actuators" :key="actuator.id" :value="actuator.id">
                {{ actuator.name || actuator.id }} ({{ actuator.ip }})
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="modalText.scheduleType" field="schedule_type" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-select v-model="form.schedule_type" :placeholder="modalText.selectValue">
              <a-option v-for="option in scheduleOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'once'" :label="modalText.executionTime" field="once_datetime" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-date-picker v-model="form.once_datetime" show-time format="YYYY-MM-DD HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'daily'" :label="modalText.executionTime" field="daily_time" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-time-picker v-model="form.daily_time" format="HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'hourly'" :label="modalText.hourlyMinute" field="hourly_minute" :rules="[{ required: true, message: modalText.enterValue }]">
            <a-input-number v-model="form.hourly_minute" :min="0" :max="59" placeholder="0-59" style="width: 100%">
              <template #suffix>{{ modalText.minuteSuffix }}</template>
            </a-input-number>
          </a-form-item>
        </div>

        <div v-if="form.module !== 'ui_automation'" class="form-row">
          <a-form-item :label="modalText.scheduleType" field="schedule_type" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-select v-model="form.schedule_type" :placeholder="modalText.selectValue">
              <a-option v-for="option in scheduleOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'once'" :label="modalText.executionTime" field="once_datetime" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-date-picker v-model="form.once_datetime" show-time format="YYYY-MM-DD HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'daily'" :label="modalText.executionTime" field="daily_time" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-time-picker v-model="form.daily_time" format="HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'hourly'" :label="modalText.hourlyMinute" field="hourly_minute" :rules="[{ required: true, message: modalText.enterValue }]">
            <a-input-number v-model="form.hourly_minute" :min="0" :max="59" placeholder="0-59" style="width: 100%">
              <template #suffix>{{ modalText.minuteSuffix }}</template>
            </a-input-number>
          </a-form-item>
        </div>

        <template v-if="form.schedule_type === 'weekly'">
          <a-form-item :label="modalText.selectWeekdays" field="weekly_days" :rules="[{ required: true, message: modalText.selectAtLeastOneDay }]">
            <a-checkbox-group v-model="form.weekly_days">
              <a-checkbox v-for="day in weekDayOptions" :key="day.value" :value="day.value">{{ day.label }}</a-checkbox>
            </a-checkbox-group>
          </a-form-item>
          <a-form-item :label="modalText.executionTime" field="weekly_time" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-time-picker v-model="form.weekly_time" format="HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
        </template>

        <a-form-item :label="modalText.retryOnFailure">
          <a-switch v-model="form.retry_enabled" />
        </a-form-item>
        <div v-if="form.retry_enabled" class="retry-config">
          <a-form-item :label="modalText.retryCount">
            <a-input-number v-model="form.retry_count" :min="1" :max="5" style="width: 100%" />
          </a-form-item>
          <a-form-item :label="modalText.retryInterval">
            <a-input-number v-model="form.retry_interval" :min="1" :max="30" style="width: 100%">
              <template #suffix>{{ modalText.minuteSuffix }}</template>
            </a-input-number>
          </a-form-item>
        </div>

        <a-divider>推送配置</a-divider>
        <a-form-item label="推送策略" field="push_config">
          <a-radio-group v-model="form.push_config">
            <a-radio value="always">总是推送</a-radio>
            <a-radio value="failure_only">仅失败时推送</a-radio>
            <a-radio value="disabled">不推送</a-radio>
          </a-radio-group>
        </a-form-item>

        <template v-if="form.push_config !== 'disabled'">
          <a-form-item
            label="推送地址"
            field="webhook_addresses"
            :rules="[{ required: true, message: '请至少选择一个推送地址' }]"
          >
            <a-select
              v-model="form.webhook_addresses"
              placeholder="选择推送地址"
              multiple
              allow-search
              :loading="loadingWebhooks"
              @popup-visible-change="(v: boolean) => v && loadWebhooks()"
            >
              <a-option v-for="wh in webhookList" :key="wh.id" :value="wh.id">
                {{ wh.name }}
              </a-option>
            </a-select>
          </a-form-item>

          <a-form-item label="消息内容" field="push_message_content">
            <div style="display: flex; gap: 8px; margin-bottom: 8px;">
              <a-select
                placeholder="引入模板"
                allow-search
                style="width: 240px;"
                :loading="loadingTemplates"
                @popup-visible-change="(v: boolean) => v && loadTemplates()"
                @change="onTemplateSelected"
              >
                <a-option v-for="tpl in templateList" :key="tpl.id" :value="tpl.id">
                  {{ tpl.name }}
                </a-option>
              </a-select>
            </div>
            <VariableHintPanel @insert="onInsertVariable" />
            <a-textarea
              ref="pushContentRef"
              v-model="form.push_message_content"
              placeholder="支持 Markdown 和 {{变量}} 占位符"
              :auto-size="{ minRows: 6, maxRows: 15 }"
              style="font-family: monospace;"
            />
          </a-form-item>
        </template>
      </a-form>
    </div>
  </a-modal>
  <UiTestCaseSelectModal ref="caseSelectModal" :project-id="projectId" @confirm="onCaseSelected" />
  <a-modal
    v-model:visible="appUiScriptModalVisible"
    title="选择APPUI脚本"
    :width="600"
    @ok="onAppUiScriptsConfirmed"
  >
    <a-table
      :data="appUiScripts"
      row-key="id"
      :pagination="false"
      :row-selection="{ type: 'checkbox', showCheckedAll: true }"
      v-model:selectedKeys="selectedAppUiScriptIds"
    >
      <template #columns>
        <a-table-column title="脚本名称" data-index="name" />
        <a-table-column title="平台" data-index="platform" />
        <a-table-column title="等级" data-index="level" />
      </template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { IconSelectAll } from '@arco-design/web-vue/es/icon';
import axios from 'axios';
import { API_BASE_URL } from '@/config/api';
import { useAuthStore } from '@/store/authStore';
import { useAppI18n } from '@/composables/useAppI18n';
import { getCurrentServerLanguage } from '@/utils/installLocaleAdapters';
import { createTask, updateTask, type TaskFormData, type ScheduledTask } from '../services/taskService';
import { actuatorApi, type ActuatorInfo } from '@/features/ui-automation/api';
import UiTestCaseSelectModal from './UiTestCaseSelectModal.vue';
import {
  getWebhookAddresses,
  getMessageTemplates,
  type WebhookAddress,
  type MessageTemplate,
} from '@/features/notifications/services/notificationService';
import VariableHintPanel from '@/features/notifications/components/VariableHintPanel.vue';
import { scriptApi, deviceApi } from '@/features/app-ui-automation/api';

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'success'): void;
}>();

const { isEnglish } = useAppI18n();

const modalText = computed(() => (
  isEnglish.value
    ? {
        editTask: 'Edit Scheduled Task',
        createTask: 'Create Scheduled Task',
        cancel: 'Cancel',
        save: 'Save',
        taskName: 'Task Name',
        enterTaskName: 'Enter task name',
        taskNamePlaceholder: 'Example: UI-Login-Daily',
        taskDescription: 'Task Description',
        taskDescriptionPlaceholder: 'Describe what this task is for',
        module: 'Module',
        selectModule: 'Select module',
        selectValue: 'Select',
        enterValue: 'Enter a value',
        uiAutomation: 'UI Automation',
        testSuite: 'Test Suite',
        selectUiCase: 'Select UI Cases',
        selectAtLeastOneUiCase: 'Select at least one UI case',
        selectedUiCases: (count: number) => `${count} case(s) selected`,
        chooseCases: 'Choose cases',
        selectTestSuite: 'Select Test Suite',
        selectTestSuiteRequired: 'Select a test suite',
        environment: 'API Environment',
        selectEnvironment: 'Select API environment',
        selectEnvironmentRequired: 'Select an API environment',
        uiEnvironment: 'UI Environment',
        selectUiEnvironment: 'Select UI environment',
        selectUiEnvironmentRequired: 'Select a UI environment',
        actuator: 'Actuator',
        selectActuator: 'Select actuator',
        selectActuatorRequired: 'Select an actuator',
        scheduleType: 'Schedule',
        once: 'Once',
        daily: 'Daily',
        weekly: 'Weekly',
        hourly: 'Hourly',
        executionTime: 'Execution Time',
        selectTime: 'Select time',
        hourlyMinute: 'Minute of the Hour',
        minuteSuffix: 'min',
        selectWeekdays: 'Weekdays',
        selectAtLeastOneDay: 'Select at least one day',
        retryOnFailure: 'Retry on Failure',
        retryCount: 'Retry Count',
        retryInterval: 'Retry Interval',
        monday: 'Mon',
        tuesday: 'Tue',
        wednesday: 'Wed',
        thursday: 'Thu',
        friday: 'Fri',
        saturday: 'Sat',
        sunday: 'Sun',
        taskUpdated: 'Task updated',
        taskCreated: 'Task created',
        operationFailed: 'Operation failed',
      }
    : {
        editTask: '编辑定时任务',
        createTask: '新建定时任务',
        cancel: '取消',
        save: '保存',
        taskName: '任务名称',
        enterTaskName: '请输入任务名称',
        taskNamePlaceholder: '如 UI-登录页-每日',
        taskDescription: '任务描述',
        taskDescriptionPlaceholder: '用于说明任务目的',
        module: '所属模块',
        selectModule: '请选择模块',
        selectValue: '请选择',
        enterValue: '请输入',
        uiAutomation: 'UI 自动化',
        testSuite: '测试套件',
        selectUiCase: '选择UI用例',
        selectAtLeastOneUiCase: '请选择至少一个UI用例',
        selectedUiCases: (count: number) => `已选 ${count} 个用例`,
        chooseCases: '选择用例',
        selectTestSuite: '选择测试套件',
        selectTestSuiteRequired: '请选择测试套件',
        environment: 'API 环境配置',
        selectEnvironment: '请选择 API 环境配置',
        selectEnvironmentRequired: '请选择 API 环境配置',
        uiEnvironment: 'UI 环境配置',
        selectUiEnvironment: '请选择 UI 环境配置',
        selectUiEnvironmentRequired: '请选择 UI 环境配置',
        actuator: '执行器',
        selectActuator: '请选择执行器',
        selectActuatorRequired: '请选择执行器',
        scheduleType: '调度策略',
        once: '仅一次',
        daily: '每天',
        weekly: '每周',
        hourly: '每小时',
        executionTime: '执行时间',
        selectTime: '选择时间',
        hourlyMinute: '第几分钟执行',
        minuteSuffix: '分',
        selectWeekdays: '选择星期',
        selectAtLeastOneDay: '请至少选一天',
        retryOnFailure: '失败重试',
        retryCount: '重试次数',
        retryInterval: '重试间隔',
        monday: '周一',
        tuesday: '周二',
        wednesday: '周三',
        thursday: '周四',
        friday: '周五',
        saturday: '周六',
        sunday: '周日',
        taskUpdated: '任务已更新',
        taskCreated: '任务已创建',
        operationFailed: '操作失败',
      }
));

const visible = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref();

const loadingSuites = ref(false);
const loadingActuators = ref(false);
const loadingEnvironments = ref(false);
const loadingUiEnvironments = ref(false);
const testSuites = ref<{ id: number; name: string }[]>([]);
const actuators = ref<ActuatorInfo[]>([]);
const environments = ref<{ id: number; name: string; base_url: string }[]>([]);
const uiEnvironments = ref<{ id: number; name: string; browser: string }[]>([]);
const caseSelectModal = ref<InstanceType<typeof UiTestCaseSelectModal>>();

// APPUI 相关状态
const loadingAppUiDevices = ref(false);
const appUiDevices = ref<{ id: number; name: string; platform: string }[]>([]);
const appUiScriptModalVisible = ref(false);
const appUiScripts = ref<any[]>([]);
const selectedAppUiScriptIds = ref<number[]>([]);

// 推送相关状态
const loadingWebhooks = ref(false);
const webhookList = ref<WebhookAddress[]>([]);
const loadingTemplates = ref(false);
const templateList = ref<MessageTemplate[]>([]);
const pushContentRef = ref();

const scheduleOptions = computed(() => [
  { value: 'once', label: modalText.value.once },
  { value: 'daily', label: modalText.value.daily },
  { value: 'weekly', label: modalText.value.weekly },
  { value: 'hourly', label: modalText.value.hourly },
]);

const weekDayOptions = computed(() => [
  { value: 0, label: modalText.value.monday },
  { value: 1, label: modalText.value.tuesday },
  { value: 2, label: modalText.value.wednesday },
  { value: 3, label: modalText.value.thursday },
  { value: 4, label: modalText.value.friday },
  { value: 5, label: modalText.value.saturday },
  { value: 6, label: modalText.value.sunday },
]);

const defaultForm = (): TaskFormData => ({
  name: '',
  description: '',
  module: 'ui_automation',
  execution_target: 'actuator',
  schedule_type: 'daily',
  once_datetime: null,
  daily_time: null,
  weekly_days: [],
  weekly_time: null,
  hourly_minute: null,
  retry_enabled: false,
  retry_count: 3,
  retry_interval: 2,
  test_suite: null,
  ui_testcase_ids: [],
  actuator_id: '',
  environment: null,
  ui_environment: null,
  app_ui_scripts: [],
  app_ui_device: null,
  push_config: 'always',
  webhook_addresses: [],
  push_message_content: '',
});

const form = reactive<TaskFormData>(defaultForm());

const modalTitle = computed(() => (
  isEditing.value ? modalText.value.editTask : modalText.value.createTask
));

const selectedUiCasesText = computed(() => (
  form.ui_testcase_ids.length
    ? modalText.value.selectedUiCases(form.ui_testcase_ids.length)
    : modalText.value.chooseCases
));

const selectedAppUiScriptsText = computed(() => (
  form.app_ui_scripts?.length
    ? `已选 ${form.app_ui_scripts.length} 个脚本`
    : '选择脚本'
));

const environmentValidator = (value: unknown, callback: (error?: string) => void) => {
  if (!value || value === 0) {
    callback(modalText.value.selectEnvironmentRequired);
    return;
  }
  callback();
};

const getHeaders = () => {
  const authStore = useAuthStore();
  return {
    Authorization: `Bearer ${authStore.getAccessToken}`,
    'Accept-Language': getCurrentServerLanguage(),
  };
};

const loadTestSuites = async () => {
  loadingSuites.value = true;
  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${props.projectId}/test-suites/`, {
      headers: getHeaders(),
    });
    const responseData = response.data;
    let list: any[] = [];
    if (responseData?.status === 'success') {
      list = Array.isArray(responseData.data) ? responseData.data : responseData.data?.results || [];
    } else {
      list = responseData?.results || responseData?.data || [];
    }
    testSuites.value = list.map((suite: any) => ({ id: suite.id, name: suite.name }));
  } catch {
    testSuites.value = [];
  } finally {
    loadingSuites.value = false;
  }
};

const loadActuators = async () => {
  loadingActuators.value = true;
  try {
    const res = await actuatorApi.list();
    const innerData = (res as any).data?.data?.data;
    actuators.value = (innerData?.items || []).filter((actuator: ActuatorInfo) => actuator.is_open);
  } catch {
    actuators.value = [];
  } finally {
    loadingActuators.value = false;
  }
};

const loadEnvironments = async () => {
  loadingEnvironments.value = true;
  try {
    const response = await axios.get(
      `${API_BASE_URL}/projects/${props.projectId}/api-environments/`,
      { headers: getHeaders() }
    );
    const responseData = response.data;
    let list: any[] = [];
    if (responseData?.status === 'success') {
      list = Array.isArray(responseData.data)
        ? responseData.data
        : responseData.data?.results || [];
    } else {
      list = responseData?.results || responseData?.data || [];
    }
    environments.value = list
      .filter((env: any) => env.is_active !== false)
      .map((env: any) => ({ id: env.id, name: env.name, base_url: env.base_url }));
  } catch {
    environments.value = [];
  } finally {
    loadingEnvironments.value = false;
  }
};

const loadUiEnvironments = async () => {
  loadingUiEnvironments.value = true;
  try {
    const response = await axios.get(
      `${API_BASE_URL}/ui-automation/env-configs/`,
      {
        headers: getHeaders(),
        params: { project: props.projectId, page_size: 200 },
      }
    );
    const responseData = response.data;
    let list: any[] = [];
    if (responseData?.status === 'success' && responseData.data) {
      list = Array.isArray(responseData.data)
        ? responseData.data
        : responseData.data?.results || [];
    } else if (Array.isArray(responseData)) {
      list = responseData;
    } else if (responseData?.results) {
      list = responseData.results;
    }
    // 全部展示，不再按 is_default 过滤
    uiEnvironments.value = list.map((env: any) => ({
      id: env.id,
      name: env.name,
      browser: env.browser,
    }));
  } catch {
    uiEnvironments.value = [];
  } finally {
    loadingUiEnvironments.value = false;
  }
};

const onModuleChange = () => {
  form.test_suite = null;
  form.ui_testcase_ids = [];
  form.actuator_id = '';
  form.app_ui_scripts = [];
  form.app_ui_device = null;
};

const loadAppUiDevices = async () => {
  loadingAppUiDevices.value = true;
  try {
    const resp = await deviceApi.list({ project: props.projectId });
    const data = (resp as any).data?.data?.data || (resp as any).data?.data || {};
    appUiDevices.value = (data.items || data.results || []).map((d: any) => ({
      id: d.id, name: d.name, platform: d.platform,
    }));
  } catch {
    appUiDevices.value = [];
  } finally {
    loadingAppUiDevices.value = false;
  }
};

const loadAppUiScripts = async () => {
  try {
    const resp = await scriptApi.list({ project: props.projectId });
    const data = (resp as any).data?.data?.data || (resp as any).data?.data || {};
    appUiScripts.value = data.items || data.results || [];
  } catch {
    appUiScripts.value = [];
  }
};

const openAppUiScriptModal = async () => {
  await loadAppUiScripts();
  appUiScriptModalVisible.value = true;
};

const loadWebhooks = async () => {
  loadingWebhooks.value = true;
  try {
    const data = await getWebhookAddresses();
    webhookList.value = data as WebhookAddress[];
  } catch {
    webhookList.value = [];
  } finally {
    loadingWebhooks.value = false;
  }
};

const loadTemplates = async () => {
  loadingTemplates.value = true;
  try {
    templateList.value = await getMessageTemplates();
  } catch {
    templateList.value = [];
  } finally {
    loadingTemplates.value = false;
  }
};

const onTemplateSelected = (tplId: number) => {
  const tpl = templateList.value.find(t => t.id === tplId);
  if (tpl) {
    if (form.push_message_content) {
      Modal.confirm({
        title: '确认覆盖',
        content: '是否用模板内容覆盖当前消息内容？',
        onOk: () => {
          form.push_message_content = tpl.content;
        },
      });
    } else {
      form.push_message_content = tpl.content;
    }
  }
};

const onInsertVariable = (varName: string) => {
  const insertion = `{{${varName}}}`;
  const textarea = pushContentRef.value?.$el?.querySelector('textarea');
  if (textarea) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    form.push_message_content = (form.push_message_content || '').substring(0, start)
      + insertion + (form.push_message_content || '').substring(end);
    nextTick(() => {
      textarea.focus();
      const newPos = start + insertion.length;
      textarea.setSelectionRange(newPos, newPos);
    });
  } else {
    form.push_message_content = (form.push_message_content || '') + insertion;
  }
};

const onAppUiScriptsConfirmed = () => {
  form.app_ui_scripts = [...selectedAppUiScriptIds.value];
  appUiScriptModalVisible.value = false;
};

const resetForm = () => {
  Object.assign(form, defaultForm());
};

const openCaseSelectModal = () => {
  caseSelectModal.value?.open(form.ui_testcase_ids);
};

const onCaseSelected = (ids: number[]) => {
  form.ui_testcase_ids = ids;
};

const open = (task?: ScheduledTask) => {
  resetForm();
  loadEnvironments();
  loadUiEnvironments();

  if (task) {
    isEditing.value = true;
    editingId.value = task.id;
    Object.assign(form, {
      name: task.name,
      description: task.description,
      module: task.module,
      execution_target: task.execution_target,
      schedule_type: task.schedule_type,
      once_datetime: task.once_datetime,
      daily_time: task.daily_time,
      weekly_days: task.weekly_days || [],
      weekly_time: task.weekly_time,
      hourly_minute: task.hourly_minute,
      retry_enabled: task.retry_enabled,
      retry_count: task.retry_count,
      retry_interval: task.retry_interval,
      test_suite: task.test_suite,
      ui_testcase_ids: task.ui_testcase_ids || [],
      actuator_id: task.actuator_id || '',
      environment: task.environment ?? 0,
      ui_environment: task.ui_environment ?? null,
      app_ui_scripts: task.app_ui_scripts || [],
      app_ui_device: task.app_ui_device ?? null,
      push_config: task.push_config || 'always',
      webhook_addresses: task.webhook_addresses || [],
      push_message_content: task.push_message_content || '',
    });
    if (task.module === 'app_ui_automation') {
      loadAppUiDevices();
    }
  } else {
    isEditing.value = false;
    editingId.value = null;
  }
  visible.value = true;
};

const handleSubmit = async () => {
  const errors = await formRef.value?.validate();
  if (errors) return;

  submitting.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await updateTask(props.projectId, editingId.value, { ...form });
      Message.success(modalText.value.taskUpdated);
    } else {
      await createTask(props.projectId, { ...form });
      Message.success(modalText.value.taskCreated);
    }
    visible.value = false;
    emit('success');
  } catch (error: any) {
    const message = error.response?.data?.detail || error.response?.data?.error || modalText.value.operationFailed;
    Message.error(typeof message === 'string' ? message : JSON.stringify(message));
  } finally {
    submitting.value = false;
  }
};

const handleClose = () => {
  visible.value = false;
  resetForm();
};

defineExpose({ open });
</script>

<style scoped>
.form-scroll-area {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-row-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

.retry-config {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 12px;
  background: var(--color-fill-1);
  border-radius: 8px;
  margin-bottom: 16px;
}

.retry-config :deep(.arco-form-item) {
  margin-bottom: 0;
}

.form-scroll-area :deep(.arco-form-item) {
  margin-bottom: 12px;
}
</style>
