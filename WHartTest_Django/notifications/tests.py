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
        templates = list(MessageTemplate.objects.all())
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
        self.assertEqual(len(results), 2)

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
