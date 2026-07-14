## Task 3: Notifications API (serializers + views + urls + tests)

**Files:**
- Create: `WHartTest_Django/notifications/serializers.py`
- Create: `WHartTest_Django/notifications/views.py`
- Create: `WHartTest_Django/notifications/urls.py`
- Create: `WHartTest_Django/notifications/services.py` (minimal stub, expanded in Task 4)
- Modify: `WHartTest_Django/wharttest_django/urls.py`
- Modify: `WHartTest_Django/notifications/tests.py`

**Interfaces:**
- Produces: `WebhookAddressSerializer`, `MessageTemplateSerializer`, `WebhookAddressViewSet`, `MessageTemplateViewSet`, API routes under `api/notifications/`
- Consumes: `WebhookAddress`, `MessageTemplate` models, DRF

- [ ] **Step 1: Write the failing test**

Append to `WHartTest_Django/notifications/tests.py`:

```python
from rest_framework.test import APIClient
from rest_framework import status


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
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
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
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd WHartTest_Django && python manage.py test notifications -v 2
```

Expected: URL routing errors / 404s because `notifications.urls` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `WHartTest_Django/notifications/serializers.py`:

```python
from rest_framework import serializers
from .models import WebhookAddress, MessageTemplate


class WebhookAddressSerializer(serializers.ModelSerializer):
    """管理员看全部字段，普通用户仅 id/name/is_active"""

    class Meta:
        model = WebhookAddress
        fields = [
            'id', 'name', 'url', 'platform_type', 'description',
            'is_active', 'creator', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'creator', 'created_at', 'updated_at']


class WebhookAddressLimitedSerializer(serializers.ModelSerializer):
    """普通用户使用的精简序列化器（隐藏 url）"""

    class Meta:
        model = WebhookAddress
        fields = ['id', 'name', 'is_active']
        read_only_fields = fields


class MessageTemplateSerializer(serializers.ModelSerializer):
    """消息模板序列化器，is_system 只读"""

    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'name', 'content', 'platform_type', 'description',
            'is_system', 'creator', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_system', 'creator', 'created_at', 'updated_at']
```

Create `WHartTest_Django/notifications/views.py`:

```python
import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .models import WebhookAddress, MessageTemplate
from .serializers import (
    WebhookAddressSerializer,
    WebhookAddressLimitedSerializer,
    MessageTemplateSerializer,
)
from .services import build_feishu_card
import requests as http_requests

logger = logging.getLogger(__name__)


class IsAdminOrReadOnlyName(permissions.BasePermission):
    """管理员可完整CRUD；普通用户仅可GET列表（精简字段）"""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff or request.user.is_superuser


class IsCreatorOrAdmin(permissions.BasePermission):
    """创建者或管理员可编辑/删除；所有认证用户可读和创建"""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_superuser or request.user.is_staff:
            return True
        return obj.creator_id == request.user.id


class WebhookAddressViewSet(viewsets.ModelViewSet):
    """推送地址视图集"""

    queryset = WebhookAddress.objects.all()
    permission_classes = [IsAdminOrReadOnlyName]

    def get_serializer_class(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return WebhookAddressSerializer
        return WebhookAddressLimitedSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=['post'], url_path='test')
    def test_send(self, request, pk=None):
        """发送测试消息到该 webhook 地址"""
        addr = self.get_object()
        test_content = '## 推送测试\n这是一条测试消息，用于验证 Webhook 配置是否正确。'
        card = build_feishu_card(test_content, 'success', '', '')
        try:
            resp = http_requests.post(addr.url, json=card, timeout=10)
            if resp.status_code == 200:
                return Response({'message': '测试消息发送成功'}, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'message': f'发送失败，状态码: {resp.status_code}'},
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            return Response(
                {'message': f'发送失败: {str(e)}'},
                status=status.HTTP_200_OK,
            )


class MessageTemplateViewSet(viewsets.ModelViewSet):
    """消息模板视图集"""

    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsCreatorOrAdmin]

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError('系统内置模板不可删除')
        instance.delete()
```

Create `WHartTest_Django/notifications/urls.py`:

```python
from rest_framework.routers import DefaultRouter
from .views import WebhookAddressViewSet, MessageTemplateViewSet

router = DefaultRouter()
router.register(r'webhook-addresses', WebhookAddressViewSet, basename='webhook-address')
router.register(r'message-templates', MessageTemplateViewSet, basename='message-template')

urlpatterns = router.urls
```

Create `WHartTest_Django/notifications/services.py` (minimal stub, expanded in Task 4):

```python
"""推送服务模块 - Task 4 中完善"""


def build_feishu_card(rendered_content, status, report_url, task_url):
    """构建飞书交互卡片 JSON（占位实现，Task 4 完善）"""
    return {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': '测试任务执行通知'},
                'template': 'green' if status == 'success' else 'red',
            },
            'elements': [
                {
                    'tag': 'markdown',
                    'content': rendered_content,
                },
            ],
        },
    }
```

Register in `WHartTest_Django/wharttest_django/urls.py`. Add after the APPUI automation URL include (after line ~171):

```python
    # 挂载 APPUI 自动化路由。
    path("api/app-ui-automation/", include("app_ui_automation.urls")),
    # 挂载推送通知路由。
    path("api/notifications/", include("notifications.urls")),
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd WHartTest_Django && python manage.py test notifications -v 2
```

Expected: All tests pass (model tests + API tests).

- [ ] **Step 5: Commit**

```bash
cd WHartTest_Django && git add notifications/ wharttest_django/urls.py && git commit -m "feat: add notifications API with serializers, views, and urls"
```
