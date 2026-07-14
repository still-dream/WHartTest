## Task 5: ScheduledTask push fields + serializer extensions + tests

**Files:**
- Modify: `WHartTest_Django/task_center/models.py`
- Modify: `WHartTest_Django/task_center/serializers.py`
- Create: `WHartTest_Django/task_center/tests/__init__.py`
- Create: `WHartTest_Django/task_center/tests/test_push_serializer.py`

**Interfaces:**
- Produces: `ScheduledTask.PushConfig` enum, `push_config`/`webhook_addresses`/`push_message_content` fields, serializer extensions
- Consumes: `WebhookAddress` model, `AppUiScript`/`AppUiDevice` models

- [ ] **Step 1: Write the failing test**

Create `WHartTest_Django/task_center/tests/__init__.py` (empty file).

Create `WHartTest_Django/task_center/tests/test_push_serializer.py`:

```python
from django.test import TestCase
from django.contrib.auth.models import User
from projects.models import Project
from task_center.models import ScheduledTask
from task_center.serializers import ScheduledTaskSerializer
from notifications.models import WebhookAddress


class ScheduledTaskPushSerializerTest(TestCase):
    """ScheduledTaskSerializer 推送字段测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='s_user', password='pass1234')
        self.project = Project.objects.create(name='s_project')
        self.webhook = WebhookAddress.objects.create(
            name='hook1', url='https://open.feishu.cn/hook/x', creator=self.user,
        )

    def _get_context(self):
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.post('/')
        request.user = self.user
        return {'request': request, 'project': self.project}

    def test_push_config_default_value(self):
        task = ScheduledTask.objects.create(
            name='default_push', project=self.project,
            module='test_suite', schedule_type='daily',
            daily_time='10:00:00', creator=self.user,
        )
        self.assertEqual(task.push_config, 'always')
        self.assertEqual(task.push_message_content, '')

    def test_serializer_includes_push_fields(self):
        task = ScheduledTask.objects.create(
            name='push_task', project=self.project,
            module='test_suite', schedule_type='daily',
            daily_time='10:00:00', creator=self.user,
            push_config='failure_only',
            push_message_content='## {{task_name}}',
        )
        task.webhook_addresses.add(self.webhook)
        serializer = ScheduledTaskSerializer(task)
        data = serializer.data
        self.assertIn('push_config', data)
        self.assertIn('webhook_addresses', data)
        self.assertIn('push_message_content', data)
        self.assertEqual(data['push_config'], 'failure_only')
        self.assertEqual(data['push_message_content'], '## {{task_name}}')
        self.assertIn(self.webhook.id, data['webhook_addresses'])

    def test_serializer_includes_app_ui_fields(self):
        task = ScheduledTask.objects.create(
            name='appui_task', project=self.project,
            module='app_ui_automation', schedule_type='daily',
            daily_time='10:00:00', creator=self.user,
        )
        serializer = ScheduledTaskSerializer(task)
        data = serializer.data
        self.assertIn('app_ui_scripts', data)
        self.assertIn('app_ui_device', data)

    def test_validate_app_ui_requires_scripts_and_device(self):
        data = {
            'name': 'no_scripts', 'module': 'app_ui_automation',
            'schedule_type': 'daily', 'daily_time': '10:00:00',
            'push_config': 'disabled',
        }
        serializer = ScheduledTaskSerializer(data=data, context=self._get_context())
        self.assertFalse(serializer.is_valid())

    def test_validate_push_config_requires_content_and_webhooks(self):
        data = {
            'name': 'push_no_content', 'module': 'test_suite',
            'schedule_type': 'daily', 'daily_time': '10:00:00',
            'push_config': 'always',
            'push_message_content': '',
            'webhook_addresses': [],
        }
        serializer = ScheduledTaskSerializer(data=data, context=self._get_context())
        self.assertFalse(serializer.is_valid())

    def test_validate_push_disabled_allows_empty_content(self):
        data = {
            'name': 'push_disabled', 'module': 'test_suite',
            'schedule_type': 'daily', 'daily_time': '10:00:00',
            'push_config': 'disabled',
            'push_message_content': '',
            'webhook_addresses': [],
        }
        serializer = ScheduledTaskSerializer(data=data, context=self._get_context())
        if not serializer.is_valid():
            self.assertNotIn('push_message_content', serializer.errors)
            self.assertNotIn('webhook_addresses', serializer.errors)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd WHartTest_Django && python manage.py test task_center.tests.test_push_serializer -v 2
```

Expected: `AttributeError: 'ScheduledTask' object has no attribute 'push_config'`.

- [ ] **Step 3: Write minimal implementation**

**3a. Add PushConfig enum and fields to `ScheduledTask` in `WHartTest_Django/task_center/models.py`**

Add the `PushConfig` enum inside the `ScheduledTask` class, after the `ExecutionTarget` class (after line ~30):

```python
    class PushConfig(models.TextChoices):
        ALWAYS = 'always', '总是推送'
        FAILURE_ONLY = 'failure_only', '仅失败时推送'
        DISABLED = 'disabled', '不推送'
```

Add the push fields after the `celery_task_id` field (after line ~130, before the `creator` field):

```python
    # 推送配置
    push_config = models.CharField(
        '推送策略', max_length=20,
        choices=PushConfig.choices, default='always'
    )
    webhook_addresses = models.ManyToManyField(
        'notifications.WebhookAddress', blank=True,
        verbose_name='推送地址',
        related_name='scheduled_tasks',
        help_text='订阅的飞书 Webhook 推送地址'
    )
    push_message_content = models.TextField(
        '推送消息内容', blank=True, default='',
        help_text='Markdown格式，支持{{变量}}'
    )
```

**3b. Update `WHartTest_Django/task_center/serializers.py`**

Replace the imports and `ScheduledTaskSerializer` with the extended version:

```python
from rest_framework import serializers
from .models import ScheduledTask, TaskExecution
from ui_automation.models import UiTestCase
from app_ui_automation.models import AppUiScript, AppUiDevice
from notifications.models import WebhookAddress


class ScheduledTaskSerializer(serializers.ModelSerializer):
    schedule_display = serializers.SerializerMethodField()
    creator_name = serializers.SerializerMethodField()
    test_suite_name = serializers.SerializerMethodField()
    environment_name = serializers.SerializerMethodField()
    ui_environment_name = serializers.SerializerMethodField()
    ui_testcase_ids = serializers.PrimaryKeyRelatedField(
        source='ui_testcases', many=True,
        queryset=UiTestCase.objects.all(), required=False
    )
    app_ui_scripts = serializers.PrimaryKeyRelatedField(
        many=True, queryset=AppUiScript.objects.all(), required=False
    )
    app_ui_device = serializers.PrimaryKeyRelatedField(
        queryset=AppUiDevice.objects.all(), required=False, allow_null=True
    )
    webhook_addresses = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=WebhookAddress.objects.filter(is_active=True),
        required=False
    )

    class Meta:
        model = ScheduledTask
        fields = [
            'id', 'name', 'description', 'project', 'module',
            'execution_target', 'schedule_type', 'once_datetime',
            'daily_time', 'weekly_days', 'weekly_time', 'hourly_minute',
            'retry_enabled', 'retry_count', 'retry_interval',
            'status', 'last_run_at', 'creator', 'creator_name',
            'schedule_display', 'created_at', 'updated_at',
            'test_suite', 'test_suite_name', 'ui_testcase_ids',
            'actuator_id',
            'environment', 'environment_name',
            'ui_environment', 'ui_environment_name',
            'app_ui_scripts', 'app_ui_device',
            'push_config', 'webhook_addresses', 'push_message_content',
        ]
        read_only_fields = [
            'project', 'status', 'last_run_at', 'creator', 'creator_name',
            'schedule_display', 'created_at', 'updated_at',
            'test_suite_name', 'environment_name', 'ui_environment_name',
        ]
        extra_kwargs = {
            'environment': {'required': False, 'allow_null': True},
            'ui_environment': {'required': False, 'allow_null': True},
        }
```

Add the push validation rules inside the `validate` method, before `return attrs`:

```python
        # APPUI 自动化模块校验
        if module == ScheduledTask.TaskModule.APP_UI_AUTOMATION:
            app_ui_scripts = attrs.get('app_ui_scripts', None)
            if app_ui_scripts is not None:
                if hasattr(app_ui_scripts, 'all'):
                    script_count = app_ui_scripts.count()
                elif isinstance(app_ui_scripts, list):
                    script_count = len(app_ui_scripts)
                else:
                    script_count = 0
            elif self.instance:
                script_count = self.instance.app_ui_scripts.count()
            else:
                script_count = 0
            if not script_count:
                raise serializers.ValidationError({'app_ui_scripts': 'APPUI 自动化模块必须选择至少一个脚本'})

            app_ui_device = attrs.get('app_ui_device', getattr(self.instance, 'app_ui_device_id', None) if self.instance else None)
            if not app_ui_device:
                raise serializers.ValidationError({'app_ui_device': 'APPUI 自动化模块必须选择执行设备'})

        # 推送配置校验
        push_config = attrs.get('push_config', getattr(self.instance, 'push_config', 'always') if self.instance else 'always')
        if push_config != 'disabled':
            push_content = attrs.get('push_message_content', getattr(self.instance, 'push_message_content', '') if self.instance else '')
            if not push_content:
                raise serializers.ValidationError({'push_message_content': '启用推送时必须填写消息内容'})
            webhooks = attrs.get('webhook_addresses', None)
            if webhooks is not None:
                webhook_count = len(webhooks) if isinstance(webhooks, list) else 0
            elif self.instance:
                webhook_count = self.instance.webhook_addresses.count()
            else:
                webhook_count = 0
            if webhook_count == 0:
                raise serializers.ValidationError({'webhook_addresses': '启用推送时至少选择一个推送地址'})
```

- [ ] **Step 4: Run makemigrations + migrate**

```bash
cd WHartTest_Django && python manage.py makemigrations task_center && python manage.py migrate
```

Expected: Migration `0009_scheduledtask_push_config_and_more` created.

- [ ] **Step 5: Run test to verify it passes**

```bash
cd WHartTest_Django && python manage.py test task_center.tests.test_push_serializer -v 2
```

Expected: All 6 tests pass.

- [ ] **Step 6: Commit**

```bash
cd WHartTest_Django && git add task_center/ && git commit -m "feat: add push config fields and serializer extensions to ScheduledTask"
```
