## Task 10: Frontend TaskFormModal modifications + router + menu

**Files:**
- Modify: `WHartTest_Vue/src/features/task-center/services/taskService.ts`
- Modify: `WHartTest_Vue/src/features/task-center/components/TaskFormModal.vue`
- Modify: `WHartTest_Vue/src/router/index.ts`

**Interfaces:**
- Produces: Extended TaskFormModal with APPUI + push config, new routes
- Consumes: notificationService, app-ui-automation API, VariableHintPanel

- [ ] **Step 1: Update taskService.ts types**

In `WHartTest_Vue/src/features/task-center/services/taskService.ts`, update the `TaskModule` type (line 9):

```typescript
export type TaskModule = 'ui_automation' | 'test_suite' | 'app_ui_automation';
```

Add `PushConfig` type after `ExecutionStatus` (line 11):

```typescript
export type PushConfig = 'always' | 'failure_only' | 'disabled';
```

Update the `ScheduledTask` interface to add new fields (after `ui_environment_name`):

```typescript
export interface ScheduledTask {
  id: number;
  name: string;
  description: string;
  project: number;
  module: TaskModule;
  execution_target: string;
  schedule_type: ScheduleType;
  once_datetime: string | null;
  daily_time: string | null;
  weekly_days: number[];
  weekly_time: string | null;
  hourly_minute: number | null;
  retry_enabled: boolean;
  retry_count: number;
  retry_interval: number;
  status: TaskStatus;
  last_run_at: string | null;
  creator: number | null;
  creator_name: string | null;
  schedule_display: string;
  test_suite: number | null;
  test_suite_name: string | null;
  ui_testcase_ids: number[];
  actuator_id: string;
  environment: number | null;
  environment_name: string | null;
  ui_environment: number | null;
  ui_environment_name: string | null;
  app_ui_scripts: number[];
  app_ui_device: number | null;
  push_config: PushConfig;
  webhook_addresses: number[];
  push_message_content: string;
  created_at: string;
  updated_at: string;
}
```

Update the `TaskFormData` interface to add new fields:

```typescript
export interface TaskFormData {
  name: string;
  description: string;
  module: TaskModule;
  execution_target: string;
  schedule_type: ScheduleType;
  once_datetime?: string | null;
  daily_time?: string | null;
  weekly_days?: number[];
  weekly_time?: string | null;
  hourly_minute?: number | null;
  retry_enabled: boolean;
  retry_count: number;
  retry_interval: number;
  test_suite?: number | null;
  ui_testcase_ids?: number[];
  actuator_id?: string;
  environment: number;
  ui_environment?: number | null;
  app_ui_scripts?: number[];
  app_ui_device?: number | null;
  push_config?: PushConfig;
  webhook_addresses?: number[];
  push_message_content?: string;
}
```

- [ ] **Step 2: Modify TaskFormModal.vue**

In `WHartTest_Vue/src/features/task-center/components/TaskFormModal.vue`, make the following changes:

**2a. Add imports** (after existing imports in the `<script setup>` section):

```typescript
import {
  getWebhookAddresses,
  getMessageTemplates,
  type WebhookAddress,
  type MessageTemplate,
} from '@/features/notifications/services/notificationService';
import VariableHintPanel from '@/features/notifications/components/VariableHintPanel.vue';
import { scriptApi, deviceApi } from '@/features/app-ui-automation/api';
```

**2b. Add module option** in the template, after the `test_suite` option:

```html
            <a-select v-model="form.module" :placeholder="modalText.selectModule" @change="onModuleChange">
              <a-option value="ui_automation">{{ modalText.uiAutomation }}</a-option>
              <a-option value="test_suite">{{ modalText.testSuite }}</a-option>
              <a-option value="app_ui_automation">APPUI 自动化</a-option>
            </a-select>
```

**2c. Add APPUI script selection** (after the test_suite form-item, before the closing `</div>` of `form-row`):

```html
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
```

**2d. Add APPUI device dropdown** (after the APPUI script form-item, still within the form-row div):

```html
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
```

**2e. Add push config section** (after the retry config section, before `</a-form>`):

```html
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
```

**2f. Add reactive state and functions** in the `<script setup>` section:

```typescript
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

const selectedAppUiScriptsText = computed(() => (
  form.app_ui_scripts?.length
    ? `已选 ${form.app_ui_scripts.length} 个脚本`
    : '选择脚本'
));
```

Add to `defaultForm()`:

```typescript
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
```

Add load functions:

```typescript
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
```

Add `nextTick` and `Modal` to imports:

```typescript
import { ref, reactive, computed, nextTick } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
```

Update `onModuleChange` to clear APPUI fields:

```typescript
const onModuleChange = () => {
  form.test_suite = null;
  form.ui_testcase_ids = [];
  form.actuator_id = '';
  form.app_ui_scripts = [];
  form.app_ui_device = null;
};
```

Update the `open` function to load APPUI data when editing an APPUI task and to set push fields:

```typescript
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
```

Add the APPUI script selection modal at the end of the template (after `<UiTestCaseSelectModal>`):

```html
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
      :row-selection="{ type: 'checkbox', showCheckedAll }"
      v-model:selectedKeys="selectedAppUiScriptIds"
    >
      <template #columns>
        <a-table-column title="脚本名称" data-index="name" />
        <a-table-column title="平台" data-index="platform" />
        <a-table-column title="等级" data-index="level" />
      </template>
    </a-table>
  </a-modal>
```

Add the confirm handler:

```typescript
const onAppUiScriptsConfirmed = () => {
  form.app_ui_scripts = [...selectedAppUiScriptIds.value];
  appUiScriptModalVisible.value = false;
};
```

- [ ] **Step 3: Add routes in router/index.ts**

In `WHartTest_Vue/src/router/index.ts`, add imports at the top (after the TaskCenterView import):

```typescript
import WebhookAddressView from '@/features/notifications/views/WebhookAddressView.vue';
import MessageTemplateView from '@/features/notifications/views/MessageTemplateView.vue';
```

Add routes in the children array (after the `task-center` route, before the closing `]`):

```typescript
      {
        path: 'system/webhook-addresses',
        name: 'WebhookAddressManagement',
        component: WebhookAddressView,
        meta: { requiresAdmin: true },
      },
      {
        path: 'system/message-templates',
        name: 'MessageTemplateManagement',
        component: MessageTemplateView,
      },
```

- [ ] **Step 4: Build to verify no errors**

```bash
cd WHartTest_Vue && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
cd WHartTest_Vue && git add src/features/ && git commit -m "feat: extend TaskFormModal with APPUI module and push config, add notification routes"
```
