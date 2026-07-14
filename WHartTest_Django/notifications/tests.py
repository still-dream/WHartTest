from django.test import TestCase
from django.contrib.auth.models import User
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
