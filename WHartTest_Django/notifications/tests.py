from django.test import TestCase
from django.contrib.auth.models import User
from .models import WebhookAddress


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
