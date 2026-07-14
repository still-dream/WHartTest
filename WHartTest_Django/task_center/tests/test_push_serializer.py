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
