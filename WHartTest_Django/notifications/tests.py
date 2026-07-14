from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import WebhookAddress, MessageTemplate


class WebhookAddressModelTest(TestCase):
    """WebhookAddress 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin1', password='pass1234', is_staff=True
        )

    def test_create_webhook_address(self):
        addr = WebhookAddress.objects.create(
            name='飞书测试群',
            url='https://open.feishu.cn/open-apis/bot/v2/hook/xxx',
            creator=self.user,
        )
        self.assertEqual(addr.name, '飞书测试群')
        self.assertEqual(addr.platform_type, 'feishu')
        self.assertTrue(addr.is_active)
        self.assertEqual(addr.description, '')
        self.assertIsNotNone(addr.created_at)
        self.assertIsNotNone(addr.updated_at)

    def test_str_representation(self):
        addr = WebhookAddress.objects.create(
            name='生产报警群',
            url='https://open.feishu.cn/open-apis/bot/v2/hook/abc',
            creator=self.user,
        )
        self.assertEqual(str(addr), '生产报警群')

    def test_default_values(self):
        addr = WebhookAddress.objects.create(
            name='默认地址',
            url='https://example.com/webhook',
        )
        self.assertEqual(addr.platform_type, 'feishu')
        self.assertTrue(addr.is_active)
        self.assertIsNone(addr.creator)
        self.assertEqual(addr.description, '')

    def test_ordering(self):
        a1 = WebhookAddress.objects.create(name='first', url='https://a.com')
        a2 = WebhookAddress.objects.create(name='second', url='https://b.com')
        addrs = list(WebhookAddress.objects.all())
        self.assertEqual(addrs[0], a2)
        self.assertEqual(addrs[1], a1)

    def test_creator_set_null_on_delete(self):
        addr = WebhookAddress.objects.create(
            name='with_user', url='https://c.com', creator=self.user
        )
        self.user.delete()
        addr.refresh_from_db()
        self.assertIsNone(addr.creator)


class MessageTemplateModelTest(TestCase):
    """MessageTemplate 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='user1', password='pass1234')
        self.admin = User.objects.create_user(
            username='admin1', password='pass1234', is_staff=True
        )

    def test_create_template(self):
        tpl = MessageTemplate.objects.create(
            name='默认模板',
            content='## {{task_name}} 执行完成',
            creator=self.user,
        )
        self.assertEqual(tpl.name, '默认模板')
        self.assertEqual(tpl.platform_type, 'feishu')
        self.assertFalse(tpl.is_system)
        self.assertEqual(tpl.description, '')
        self.assertIsNotNone(tpl.created_at)

    def test_str_representation(self):
        tpl = MessageTemplate.objects.create(
            name='失败通知模板',
            content='任务失败了',
            creator=self.user,
        )
        self.assertEqual(str(tpl), '失败通知模板')

    def test_system_template_flag(self):
        tpl = MessageTemplate.objects.create(
            name='系统默认',
            content='系统内置内容',
            is_system=True,
            creator=self.admin,
        )
        self.assertTrue(tpl.is_system)

    def test_ordering_system_first(self):
        t1 = MessageTemplate.objects.create(
            name='user_tpl', content='c1', creator=self.user
        )
        t2 = MessageTemplate.objects.create(
            name='sys_tpl', content='c2', is_system=True, creator=self.admin
        )
        # 迁移也会创建系统模板，只验证本测试创建的模板排序
        templates = list(MessageTemplate.objects.filter(id__in=[t1.id, t2.id]))
        self.assertEqual(templates[0], t2)
        self.assertEqual(templates[1], t1)

    def test_creator_cascade_delete(self):
        tpl = MessageTemplate.objects.create(
            name='cascade', content='c', creator=self.user
        )
        self.user.delete()
        self.assertEqual(MessageTemplate.objects.filter(id=tpl.id).count(), 0)


class WebhookAddressAPITest(TestCase):
    """WebhookAddress API 测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin1', password='pass1234', is_staff=True
        )
        self.normal_user = User.objects.create_user(
            username='user1', password='pass1234'
        )
        self.addr = WebhookAddress.objects.create(
            name='测试群', url='https://open.feishu.cn/hook/xxx',
            creator=self.admin,
        )
        self.base_url = '/api/notifications/webhook-addresses/'

    def test_admin_can_list(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.base_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)

    def test_admin_sees_full_fields(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.base_url)
        results = resp.data.get('results', resp.data)
        item = results[0]
        self.assertIn('url', item)
        self.assertIn('description', item)
        self.assertIn('platform_type', item)

    def test_normal_user_sees_limited_fields(self):
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.get(self.base_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data)
        item = results[0]
        self.assertIn('id', item)
        self.assertIn('name', item)
        self.assertIn('is_active', item)
        self.assertNotIn('url', item)

    def test_admin_can_create(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.base_url, {
            'name': '新地址', 'url': 'https://example.com/new',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WebhookAddress.objects.count(), 2)

    def test_normal_user_cannot_create(self):
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.post(self.base_url, {
            'name': 'hack', 'url': 'https://evil.com',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(f'{self.base_url}{self.addr.id}/', {
            'name': 'updated name',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.addr.refresh_from_db()
        self.assertEqual(self.addr.name, 'updated name')

    def test_admin_can_delete(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f'{self.base_url}{self.addr.id}/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        self.assertEqual(WebhookAddress.objects.count(), 0)

    def test_normal_user_cannot_delete(self):
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.delete(f'{self.base_url}{self.addr.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_test_action(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f'{self.base_url}{self.addr.id}/test/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('message', resp.data)


class MessageTemplateAPITest(TestCase):
    """MessageTemplate API 测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin1', password='pass1234', is_staff=True
        )
        self.user1 = User.objects.create_user(username='user1', password='pass1234')
        self.user2 = User.objects.create_user(username='user2', password='pass1234')
        self.sys_tpl = MessageTemplate.objects.create(
            name='系统模板', content='系统内容', is_system=True,
            creator=self.admin,
        )
        self.user_tpl = MessageTemplate.objects.create(
            name='用户模板', content='用户内容', creator=self.user1,
        )
        self.base_url = '/api/notifications/message-templates/'

    def test_any_user_can_list(self):
        self.client.force_authenticate(user=self.user2)
        resp = self.client.get(self.base_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data)
        # 迁移会创建系统内置模板，所以总数 >= 2
        self.assertGreaterEqual(len(results), 2)
        names = [r['name'] for r in results]
        self.assertIn('系统模板', names)
        self.assertIn('用户模板', names)

    def test_any_user_can_create(self):
        self.client.force_authenticate(user=self.user2)
        resp = self.client.post(self.base_url, {
            'name': '我的模板', 'content': '内容',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_creator_can_update(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.patch(f'{self.base_url}{self.user_tpl.id}/', {
            'name': 'updated',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_non_creator_cannot_update(self):
        self.client.force_authenticate(user=self.user2)
        resp = self.client.patch(f'{self.base_url}{self.user_tpl.id}/', {
            'name': 'hacked',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_creator_can_delete_own(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.delete(f'{self.base_url}{self.user_tpl.id}/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

    def test_system_template_cannot_be_deleted(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f'{self.base_url}{self.sys_tpl.id}/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_creator_cannot_delete(self):
        self.client.force_authenticate(user=self.user2)
        resp = self.client.delete(f'{self.base_url}{self.user_tpl.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_is_system_read_only(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.post(self.base_url, {
            'name': 'try system', 'content': 'c', 'is_system': True,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertFalse(resp.data['is_system'])


from notifications.variables import VARIABLES, build_context, render_content
from notifications.services import build_feishu_card, send_task_notification
from unittest.mock import patch, MagicMock
from task_center.models import ScheduledTask, TaskExecution
from projects.models import Project


class VariablesTest(TestCase):
    """变量系统测试"""

    def test_render_content_replaces_variables(self):
        content = '## {{task_name}} 执行{{status}}\n通过率: {{pass_rate}}'
        context = {
            'task_name': '登录测试',
            'status': '成功',
            'pass_rate': '100%',
        }
        result = render_content(content, context)
        self.assertEqual(result, '## 登录测试 执行成功\n通过率: 100%')

    def test_render_content_handles_missing_variable(self):
        content = 'Hello {{name}}, {{missing}}'
        context = {'name': 'World'}
        result = render_content(content, context)
        self.assertEqual(result, 'Hello World, {{missing}}')

    def test_render_content_handles_int_values(self):
        content = '总数: {{total}}, 通过: {{passed}}'
        context = {'total': 15, 'passed': 13}
        result = render_content(content, context)
        self.assertEqual(result, '总数: 15, 通过: 13')

    def test_variables_list_contains_key_vars(self):
        var_names = [v[0] for v in VARIABLES]
        self.assertIn('task_name', var_names)
        self.assertIn('project_name', var_names)
        self.assertIn('status', var_names)
        self.assertIn('total', var_names)
        self.assertIn('passed', var_names)
        self.assertIn('failed', var_names)
        self.assertIn('pass_rate', var_names)
        self.assertIn('duration', var_names)
        self.assertIn('report_url', var_names)
        self.assertIn('task_url', var_names)

    def test_build_context_for_app_ui_module(self):
        from app_ui_automation.models import AppUiBatchExecutionRecord
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='ctx_user', password='pass')
        project = Project.objects.create(name='ctx_project')
        task = ScheduledTask.objects.create(
            name='ctx_task', project=project,
            module='app_ui_automation', schedule_type='daily',
            daily_time='10:00:00', creator=user,
        )
        execution = TaskExecution.objects.create(
            task=task, trigger_type='scheduled',
            status='success',
        )
        batch = AppUiBatchExecutionRecord.objects.create(
            name='batch', total_scripts=10, passed_scripts=8,
            failed_scripts=2, status=3, executor=user,
        )
        context = build_context(task, execution, batch)
        self.assertEqual(context['task_name'], 'ctx_task')
        self.assertEqual(context['project_name'], 'ctx_project')
        self.assertEqual(context['status'], '成功')
        self.assertEqual(context['total'], 10)
        self.assertEqual(context['passed'], 8)
        self.assertEqual(context['failed'], 2)
        self.assertEqual(context['pass_rate'], '80.0%')
        self.assertEqual(context['executor'], 'ctx_user')

    def test_build_context_failed_cases_for_app_ui(self):
        from app_ui_automation.models import (
            AppUiBatchExecutionRecord, AppUiScript, AppUiExecutionRecord,
            AppUiModule,
        )
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='fc_user', password='pass')
        project = Project.objects.create(name='fc_project')
        task = ScheduledTask.objects.create(
            name='fc_task', project=project,
            module='app_ui_automation', schedule_type='daily',
            daily_time='10:00:00', creator=user,
        )
        execution = TaskExecution.objects.create(
            task=task, trigger_type='scheduled', status='failed',
        )
        module = AppUiModule.objects.create(
            project=project, name='fc_module', level=1,
        )
        script1 = AppUiScript.objects.create(
            project=project, module=module, name='script1',
            script_file='dummy.zip', script_dir='dummy',
        )
        script2 = AppUiScript.objects.create(
            project=project, module=module, name='script2',
            script_file='dummy2.zip', script_dir='dummy2',
        )
        batch = AppUiBatchExecutionRecord.objects.create(
            name='batch', total_scripts=2, passed_scripts=0,
            failed_scripts=2, status=4, executor=user,
        )
        AppUiExecutionRecord.objects.create(
            batch=batch, script=script1, status=3, executor=user,
        )
        AppUiExecutionRecord.objects.create(
            batch=batch, script=script2, status=3, executor=user,
        )
        context = build_context(task, execution, batch)
        self.assertIn('script1', context['failed_cases'])
        self.assertIn('script2', context['failed_cases'])

    def test_build_context_no_failed_cases(self):
        from app_ui_automation.models import AppUiBatchExecutionRecord
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='nf_user', password='pass')
        project = Project.objects.create(name='nf_project')
        task = ScheduledTask.objects.create(
            name='nf_task', project=project,
            module='app_ui_automation', schedule_type='daily',
            daily_time='10:00:00', creator=user,
        )
        execution = TaskExecution.objects.create(
            task=task, trigger_type='scheduled', status='success',
        )
        batch = AppUiBatchExecutionRecord.objects.create(
            name='batch', total_scripts=5, passed_scripts=5,
            failed_scripts=0, status=2, executor=user,
        )
        context = build_context(task, execution, batch)
        self.assertEqual(context['failed_cases'], '无')


class FeishuCardTest(TestCase):
    """飞书卡片构建测试"""

    def test_build_card_success_status(self):
        card = build_feishu_card('content here', 'success', 'https://report.com', 'https://task.com')
        self.assertEqual(card['msg_type'], 'interactive')
        self.assertEqual(card['card']['header']['template'], 'green')
        self.assertEqual(card['card']['header']['title']['content'], '测试任务执行通知')
        elements = card['card']['elements']
        self.assertTrue(any(e.get('tag') == 'markdown' for e in elements))

    def test_build_card_failed_status(self):
        card = build_feishu_card('failed content', 'failed', '', '')
        self.assertEqual(card['card']['header']['template'], 'red')

    def test_build_card_has_action_buttons(self):
        card = build_feishu_card('c', 'success', 'https://r.com', 'https://t.com')
        elements = card['card']['elements']
        actions = [e for e in elements if e.get('tag') == 'action']
        self.assertTrue(len(actions) >= 1)
        buttons = actions[0].get('actions', [])
        self.assertTrue(len(buttons) >= 2)
        button_types = [b.get('type') for b in buttons]
        self.assertIn('link', button_types)


class SendTaskNotificationTest(TestCase):
    """send_task_notification 测试"""

    def setUp(self):
        from app_ui_automation.models import AppUiBatchExecutionRecord

        self.user = User.objects.create_user(username='push_user', password='pass')
        self.project = Project.objects.create(name='push_project')
        self.task = ScheduledTask.objects.create(
            name='push_task', project=self.project,
            module='app_ui_automation', schedule_type='daily',
            daily_time='10:00:00', creator=self.user,
            push_config='always',
            push_message_content='## {{task_name}} 执行{{status}}',
        )
        self.webhook = WebhookAddress.objects.create(
            name='push_hook', url='https://open.feishu.cn/hook/test',
            creator=self.user,
        )
        self.task.webhook_addresses.add(self.webhook)
        self.execution = TaskExecution.objects.create(
            task=self.task, trigger_type='scheduled', status='success',
        )
        self.batch = AppUiBatchExecutionRecord.objects.create(
            name='batch', total_scripts=3, passed_scripts=3,
            failed_scripts=0, status=2, executor=self.user,
        )

    @patch('notifications.services.http_requests.post')
    def test_send_notification_always(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        send_task_notification(self.task, self.execution, self.batch)
        self.assertTrue(mock_post.called)

    @patch('notifications.services.http_requests.post')
    def test_skip_when_disabled(self, mock_post):
        self.task.push_config = 'disabled'
        self.task.save()
        send_task_notification(self.task, self.execution, self.batch)
        self.assertFalse(mock_post.called)

    @patch('notifications.services.http_requests.post')
    def test_skip_failure_only_on_success(self, mock_post):
        self.task.push_config = 'failure_only'
        self.task.save()
        send_task_notification(self.task, self.execution, self.batch)
        self.assertFalse(mock_post.called)

    @patch('notifications.services.http_requests.post')
    def test_send_failure_only_on_failure(self, mock_post):
        self.task.push_config = 'failure_only'
        self.task.save()
        self.execution.status = 'failed'
        self.execution.save()
        self.batch.status = 4
        self.batch.failed_scripts = 3
        self.batch.passed_scripts = 0
        self.batch.save()
        send_task_notification(self.task, self.execution, self.batch)
        self.assertTrue(mock_post.called)

    @patch('notifications.services.http_requests.post')
    def test_push_failure_does_not_raise(self, mock_post):
        mock_post.side_effect = Exception('network error')
        send_task_notification(self.task, self.execution, self.batch)

    @patch('notifications.services.http_requests.post')
    def test_inactive_webhook_skipped(self, mock_post):
        self.webhook.is_active = False
        self.webhook.save()
        mock_post.return_value = MagicMock(status_code=200)
        send_task_notification(self.task, self.execution, self.batch)
        self.assertFalse(mock_post.called)


from types import SimpleNamespace


class SystemTemplateMigrationTest(TestCase):
    """系统内置模板 data migration 测试"""

    def test_system_template_exists_after_migration(self):
        sys_templates = MessageTemplate.objects.filter(is_system=True)
        self.assertTrue(sys_templates.exists())
        tpl = sys_templates.first()
        self.assertIn('{{task_name}}', tpl.content)
        self.assertIn('{{status}}', tpl.content)
        self.assertIn('{{project_name}}', tpl.content)
        self.assertIn('{{total}}', tpl.content)
        self.assertIn('{{passed}}', tpl.content)
        self.assertIn('{{failed}}', tpl.content)
        self.assertIn('{{report_url}}', tpl.content)


class AccountsMenuMappingTest(TestCase):
    """accounts 序列化器菜单分类测试"""

    def test_notifications_grouped_under_system_settings(self):
        from accounts.serializers import ContentTypeSerializer
        serializer = ContentTypeSerializer()
        ct = SimpleNamespace(app_label='notifications', model='webhookaddress')
        self.assertEqual(serializer.get_app_label_cn(ct), '系统管理')

    def test_notifications_subcategory_is_push_config(self):
        from accounts.serializers import ContentTypeSerializer
        serializer = ContentTypeSerializer()
        ct = SimpleNamespace(app_label='notifications', model='webhookaddress')
        self.assertEqual(serializer.get_app_label_subcategory(ct), '推送配置')
