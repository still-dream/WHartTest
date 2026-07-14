# Task Push Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add task push notification capability to WHartTest - webhook address management, message template library, variable rendering, Feishu card push, and APPUI automation task support in the task center.

**Architecture:** New Django app `notifications` encapsulates WebhookAddress + MessageTemplate models, serializers, views, a variables registry, and a Feishu push service. The existing `task_center` app is extended with push config fields on `ScheduledTask` and push integration in `tasks.py`. Frontend gains a new `notifications` feature module (webhook management page, template library page, reusable variable hint panel) and the existing `TaskFormModal.vue` is extended with APPUI module support and a push configuration section.

**Tech Stack:** Django 5.2, DRF, Celery, requests library (Feishu webhook HTTP), Vue 3 + TypeScript + Arco Design

## Global Constraints

- Django app name: `notifications`, registered in `INSTALLED_APPS` after `task_center`
- URL prefix: `api/notifications/`
- Push platform: Feishu only (custom bot webhook)
- Variable rendering: simple `{{var}}` string replacement - no template engine
- Push failures must NOT affect task execution results - log and continue
- Push executes synchronously within the Celery task (after execution completes, before task returns)
- Admin = `is_superuser` or `is_staff` (matches existing codebase convention)
- Backend tests use `django.test.TestCase` and `rest_framework.test.APIClient`
- Test command: `cd WHartTest_Django && python manage.py test <app_name> -v 2`
- Frontend build command: `cd WHartTest_Vue && npm run build`
- Commit messages in English, format: `feat: <description>`
- Existing migration numbering: task_center latest is `0008`, app_ui_automation latest is `0004`
- `ScheduledTask.APP_UI_AUTOMATION` module enum and `app_ui_scripts`/`app_ui_device` fields already exist in the model; only the serializer and frontend are missing them

---

## Task 1: Create notifications app + WebhookAddress model + tests

**Files:**
- Create: `WHartTest_Django/notifications/__init__.py`
- Create: `WHartTest_Django/notifications/apps.py`
- Create: `WHartTest_Django/notifications/models.py`
- Create: `WHartTest_Django/notifications/admin.py`
- Create: `WHartTest_Django/notifications/migrations/__init__.py`
- Create: `WHartTest_Django/notifications/tests.py`
- Modify: `WHartTest_Django/wharttest_django/settings.py`

**Interfaces:**
- Produces: `notifications` Django app, `WebhookAddress` model
- Consumes: `django.contrib.auth.models.User`

- [ ] **Step 1: Create app directory structure**

Create the following empty files:
- `WHartTest_Django/notifications/__init__.py` (empty)
- `WHartTest_Django/notifications/migrations/__init__.py` (empty)

- [ ] **Step 2: Create apps.py**

```python
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = '推送通知'
```

- [ ] **Step 3: Register app in INSTALLED_APPS**

In `WHartTest_Django/wharttest_django/settings.py`, add `'notifications'` after `'task_center'` (line ~136):

```python
    'task_center', # 任务中心应用
    'notifications',  # 推送通知应用
    'django_celery_beat', # Celery Beat 数据库调度器
```

- [ ] **Step 4: Write the failing test**

Create `WHartTest_Django/notifications/tests.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it fails**

```bash
cd WHartTest_Django && python manage.py test notifications -v 2
```

Expected: `ModuleNotFoundError: No module named 'notifications.models'` (or similar import error).

- [ ] **Step 6: Write minimal implementation**

Create `WHartTest_Django/notifications/models.py`:

```python
from django.db import models
from django.contrib.auth.models import User


class WebhookAddress(models.Model):
    """飞书 Webhook 推送地址（全局，仅管理员管理）"""

    PLATFORM_CHOICES = [('feishu', '飞书')]

    name = models.CharField('地址名称', max_length=100)
    url = models.URLField('Webhook URL')
    platform_type = models.CharField(
        '平台类型', max_length=20, choices=PLATFORM_CHOICES, default='feishu'
    )
    description = models.TextField('描述', blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='创建人', related_name='created_webhook_addresses'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '推送地址'
        verbose_name_plural = '推送地址'
        ordering = ['-created_at']

    def __str__(self):
        return self.name
```

Create `WHartTest_Django/notifications/admin.py`:

```python
from django.contrib import admin
from .models import WebhookAddress


@admin.register(WebhookAddress)
class WebhookAddressAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform_type', 'url', 'is_active', 'creator', 'created_at']
    list_filter = ['is_active', 'platform_type']
    search_fields = ['name', 'url']
    readonly_fields = ['created_at', 'updated_at']
```

- [ ] **Step 7: Run makemigrations + migrate**

```bash
cd WHartTest_Django && python manage.py makemigrations notifications && python manage.py migrate
```

Expected: Migration `0001_initial` created, tables applied.

- [ ] **Step 8: Run test to verify it passes**

```bash
cd WHartTest_Django && python manage.py test notifications -v 2
```

Expected: All 5 tests pass.

- [ ] **Step 9: Commit**

```bash
cd WHartTest_Django && git add notifications/ wharttest_django/settings.py && git commit -m "feat: add notifications app with WebhookAddress model"
```

---

## Task 2: MessageTemplate model + tests

**Files:**
- Modify: `WHartTest_Django/notifications/models.py`
- Modify: `WHartTest_Django/notifications/admin.py`
- Modify: `WHartTest_Django/notifications/tests.py`

**Interfaces:**
- Produces: `MessageTemplate` model
- Consumes: `django.contrib.auth.models.User`

- [ ] **Step 1: Write the failing test**

Append to `WHartTest_Django/notifications/tests.py`:

```python
from .models import WebhookAddress, MessageTemplate


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd WHartTest_Django && python manage.py test notifications.MessageTemplateModelTest -v 2
```

Expected: `ImportError: cannot import name 'MessageTemplate'` (model not yet defined).

- [ ] **Step 3: Write minimal implementation**

Append to `WHartTest_Django/notifications/models.py`:

```python
class MessageTemplate(models.Model):
    """消息模板库（所有用户可维护）"""

    PLATFORM_CHOICES = [('feishu', '飞书')]

    name = models.CharField('模板名称', max_length=100)
    content = models.TextField(
        '模板内容', help_text='Markdown格式，支持{{变量}}占位符'
    )
    platform_type = models.CharField(
        '平台类型', max_length=20, choices=PLATFORM_CHOICES, default='feishu'
    )
    description = models.TextField('描述', blank=True, default='')
    is_system = models.BooleanField('系统内置', default=False)
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE,
        verbose_name='创建人', related_name='created_message_templates'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '消息模板'
        verbose_name_plural = '消息模板'
        ordering = ['-is_system', '-created_at']

    def __str__(self):
        return self.name
```

Append to `WHartTest_Django/notifications/admin.py`:

```python
from .models import WebhookAddress, MessageTemplate


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform_type', 'is_system', 'creator', 'created_at', 'updated_at']
    list_filter = ['is_system', 'platform_type']
    search_fields = ['name', 'content']
    readonly_fields = ['created_at', 'updated_at']
```

- [ ] **Step 4: Run makemigrations + migrate**

```bash
cd WHartTest_Django && python manage.py makemigrations notifications && python manage.py migrate
```

Expected: Migration `0002_messagetemplate` created.

- [ ] **Step 5: Run test to verify it passes**

```bash
cd WHartTest_Django && python manage.py test notifications -v 2
```

Expected: All 10 tests pass (5 WebhookAddress + 5 MessageTemplate).

- [ ] **Step 6: Commit**

```bash
cd WHartTest_Django && git add notifications/ && git commit -m "feat: add MessageTemplate model"
```

---

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
cd WHartTest_Django && python manage.py test notifications.WebhookAddressAPITest notifications.MessageTemplateAPITest -v 2
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

---

## Task 4: Variables system + push service + tests

**Files:**
- Create: `WHartTest_Django/notifications/variables.py`
- Modify: `WHartTest_Django/notifications/services.py`
- Modify: `WHartTest_Django/notifications/tests.py`

**Interfaces:**
- Produces: `VARIABLES` list, `build_context()`, `render_content()`, `build_feishu_card()`, `send_task_notification()`
- Consumes: `ScheduledTask`, `TaskExecution`, `AppUiBatchExecutionRecord` models

- [ ] **Step 1: Write the failing test**

Append to `WHartTest_Django/notifications/tests.py`:

```python
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
```

> **Note:** Task 5 must be completed before these tests can run, as they depend on `push_config`, `push_message_content`, and `webhook_addresses` fields on `ScheduledTask`. Run Task 5's migration first, or run this task's tests after Task 5.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd WHartTest_Django && python manage.py test notifications.VariablesTest notifications.FeishuCardTest notifications.SendTaskNotificationTest -v 2
```

Expected: `ImportError: cannot import name 'VARIABLES'` (variables.py not yet created).

- [ ] **Step 3: Write minimal implementation**

Create `WHartTest_Django/notifications/variables.py`:

```python
"""变量注册表与上下文构建"""
from django.utils import timezone


# 变量列表：(变量名, 说明, 示例值)
VARIABLES = [
    ('task_name', '任务名称', '登录模块回归测试'),
    ('project_name', '项目名称', 'J&T Express'),
    ('status', '执行状态', '成功 / 失败'),
    ('trigger_type', '触发方式', '定时 / 手动 / API'),
    ('total', '用例总数', '15'),
    ('passed', '通过数', '13'),
    ('failed', '失败数', '2'),
    ('pass_rate', '通过率', '86.7%'),
    ('duration', '执行时长', '5分23秒'),
    ('executor', '执行人', 'admin'),
    ('failed_cases', '失败用例列表', 'test_login / test_payment'),
    ('error_summary', '错误摘要', '2个用例执行失败'),
    ('current_date', '当前日期时间', '2026-07-14 15:30:00'),
    ('report_url', '报告链接', 'https://...'),
    ('task_url', '任务详情链接', 'https://...'),
    ('platform_name', '平台名称', 'WHartTest'),
]


def render_content(content: str, context: dict) -> str:
    """简单字符串替换：将 {{key}} 替换为 context[key]"""
    for key, value in context.items():
        content = content.replace(f'{{{{{key}}}}}', str(value))
    return content


def _format_duration(seconds):
    """将秒数格式化为可读时长"""
    if seconds is None:
        return '-'
    total = int(seconds)
    if total < 60:
        return f'{total}秒'
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f'{minutes}分{secs}秒'
    hours, mins = divmod(minutes, 60)
    return f'{hours}小时{mins}分{secs}秒'


def build_context(task, execution, module_result):
    """根据任务模块类型构建变量上下文字典"""
    from task_center.models import ScheduledTask

    context = {
        'task_name': task.name,
        'project_name': task.project.name if task.project else '',
        'trigger_type': execution.get_trigger_type_display() if execution else '',
        'current_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'platform_name': 'WHartTest',
        'total': 0,
        'passed': 0,
        'failed': 0,
        'pass_rate': '0%',
        'duration': '-',
        'executor': '',
        'failed_cases': '无',
        'error_summary': '',
        'report_url': '',
        'task_url': '',
    }

    if execution:
        if execution.status == 'success':
            context['status'] = '成功'
        elif execution.status == 'failed':
            context['status'] = '失败'
        else:
            context['status'] = execution.status

        if execution.started_at and execution.finished_at:
            delta = (execution.finished_at - execution.started_at).total_seconds()
            context['duration'] = _format_duration(delta)

        if execution.task and execution.task.creator:
            context['executor'] = execution.task.creator.username
    else:
        context['status'] = '未知'

    # 根据模块类型提取统计数据
    if task.module == ScheduledTask.TaskModule.APP_UI_AUTOMATION and module_result:
        _fill_app_ui_context(context, module_result, execution)
    elif task.module == ScheduledTask.TaskModule.UI_AUTOMATION:
        _fill_ui_automation_context(context, task)
    elif task.module == ScheduledTask.TaskModule.TEST_SUITE:
        _fill_test_suite_context(context, task)

    return context


def _fill_app_ui_context(context, batch, execution):
    """从 AppUiBatchExecutionRecord 提取统计数据"""
    context['total'] = batch.total_scripts
    context['passed'] = batch.passed_scripts
    context['failed'] = batch.failed_scripts

    if batch.total_scripts > 0:
        rate = round(batch.passed_scripts / batch.total_scripts * 100, 1)
        context['pass_rate'] = f'{rate}%'

    if batch.duration:
        context['duration'] = _format_duration(batch.duration)

    if batch.failed_scripts > 0:
        failed_records = batch.execution_records.filter(status=3).select_related('script')
        failed_names = [r.script.name for r in failed_records if r.script]
        context['failed_cases'] = ' / '.join(failed_names) if failed_names else '无'
        context['error_summary'] = f'{batch.failed_scripts}个脚本执行失败'
    else:
        context['failed_cases'] = '无'
        context['error_summary'] = ''

    if batch.id:
        context['report_url'] = f'/app-ui-automation/batch-records/{batch.id}/'
    if execution and execution.task and execution.task.id:
        context['task_url'] = f'/task-center?task={execution.task.id}'


def _fill_ui_automation_context(context, task):
    """从 UI 自动化执行记录提取统计数据"""
    from ui_automation.models import UiBatchExecutionRecord
    batch_name = f"定时任务-{task.name}"
    batches = UiBatchExecutionRecord.objects.filter(name=batch_name).order_by('-created_at')
    if batches.exists():
        batch = batches.first()
        context['total'] = getattr(batch, 'total_cases', 0) or 0
        context['passed'] = getattr(batch, 'passed_cases', 0) or 0
        context['failed'] = getattr(batch, 'failed_cases', 0) or 0
        total = context['total']
        if total > 0:
            rate = round(context['passed'] / total * 100, 1)
            context['pass_rate'] = f'{rate}%'
        if context['failed'] > 0:
            context['error_summary'] = f'{context["failed"]}个用例执行失败'
    if task.id:
        context['task_url'] = f'/task-center?task={task.id}'


def _fill_test_suite_context(context, task):
    """从测试套件执行记录提取统计数据"""
    from testcases.models import TestExecution
    if task.test_suite:
        executions = TestExecution.objects.filter(suite=task.test_suite).order_by('-id')
        if executions.exists():
            exec_record = executions.first()
            total = exec_record.testcaseresult_set.count() if hasattr(exec_record, 'testcaseresult_set') else 0
            passed = exec_record.testcaseresult_set.filter(status='pass').count() if total else 0
            failed = exec_record.testcaseresult_set.filter(status='fail').count() if total else 0
            context['total'] = total
            context['passed'] = passed
            context['failed'] = failed
            if total > 0:
                rate = round(passed / total * 100, 1)
                context['pass_rate'] = f'{rate}%'
            if failed > 0:
                context['error_summary'] = f'{failed}个用例执行失败'
    if task.id:
        context['task_url'] = f'/task-center?task={task.id}'
```

Replace `WHartTest_Django/notifications/services.py` with the full implementation:

```python
"""推送服务：变量渲染 + 飞书卡片构建 + HTTP 发送"""
import logging
import requests as http_requests

from .variables import build_context, render_content

logger = logging.getLogger(__name__)


def build_feishu_card(rendered_content, status, report_url, task_url):
    """构建飞书交互卡片 JSON"""
    header_template = 'green' if status == 'success' else 'red'

    elements = [
        {
            'tag': 'markdown',
            'content': rendered_content,
        },
    ]

    actions = []
    if report_url:
        actions.append({
            'tag': 'button',
            'text': {'tag': 'plain_text', 'content': '查看完整报告'},
            'type': 'link',
            'url': report_url,
        })
    if task_url:
        actions.append({
            'tag': 'button',
            'text': {'tag': 'plain_text', 'content': '任务详情'},
            'type': 'link',
            'url': task_url,
        })
    if actions:
        elements.append({
            'tag': 'action',
            'actions': actions,
        })

    return {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {
                    'tag': 'plain_text',
                    'content': '测试任务执行通知',
                },
                'template': header_template,
            },
            'elements': elements,
        },
    }


def send_task_notification(task, execution, module_result):
    """任务执行完成后调用，发送推送通知"""
    if task.push_config == 'disabled':
        return
    if task.push_config == 'failure_only' and execution.status == 'success':
        return

    context = build_context(task, execution, module_result)
    rendered = render_content(task.push_message_content or '', context)

    for addr in task.webhook_addresses.filter(is_active=True):
        card = build_feishu_card(
            rendered,
            'success' if context['status'] == '成功' else 'failed',
            context.get('report_url', ''),
            context.get('task_url', ''),
        )
        try:
            resp = http_requests.post(addr.url, json=card, timeout=10)
            if resp.status_code != 200:
                logger.warning(
                    f"推送失败 {addr.name}: HTTP {resp.status_code}, "
                    f"response={resp.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"推送失败 {addr.name}: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd WHartTest_Django && python manage.py test notifications -v 2
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd WHartTest_Django && git add notifications/ && git commit -m "feat: add variables system, feishu card builder, and push service"
```

---

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

---

## Task 6: Push integration in tasks.py + system setup

**Files:**
- Modify: `WHartTest_Django/task_center/tasks.py`
- Modify: `WHartTest_Django/accounts/serializers.py`
- Create: `WHartTest_Django/notifications/migrations/0002_initial_system_template.py`
- Modify: `WHartTest_Django/notifications/tests.py`

**Interfaces:**
- Produces: push integration in Celery task, system template data migration, notifications menu mapping
- Consumes: `notifications.services.send_task_notification`, `notifications.models.MessageTemplate`

- [ ] **Step 1: Write the failing test**

Append to `WHartTest_Django/notifications/tests.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd WHartTest_Django && python manage.py test notifications.SystemTemplateMigrationTest notifications.AccountsMenuMappingTest -v 2
```

Expected: System template doesn't exist; menu mapping returns wrong value.

- [ ] **Step 3: Write minimal implementation**

**3a. Fix `task_center/tasks.py` APPUI branch and add push integration**

Replace the APPUI branch (the `if task.module == ScheduledTask.TaskModule.APP_UI_AUTOMATION:` block, lines ~104-131) with:

```python
        if task.module == ScheduledTask.TaskModule.APP_UI_AUTOMATION:
            from app_ui_automation.models import AppUiBatchExecutionRecord
            from app_ui_automation.tasks import execute_app_ui_batch

            scripts = task.app_ui_scripts.all()
            if not scripts:
                execution.log += 'No scripts selected for APPUI task\n'
                execution.status = TaskExecution.ExecutionStatus.FAILED
                execution.finished_at = timezone.now()
                execution.save()
                try:
                    from notifications.services import send_task_notification
                    send_task_notification(task, execution, None)
                except Exception as push_err:
                    logger.warning(f"推送通知失败: {push_err}")
                return {'status': 'failed', 'execution_id': execution.execution_id, 'error': 'No scripts selected'}

            batch = AppUiBatchExecutionRecord.objects.create(
                name=f"定时任务-{task.name}",
                total_scripts=scripts.count(),
                trigger_type='scheduled',
                executor=task.creator,
                start_time=timezone.now(),
            )

            script_ids = list(scripts.values_list('id', flat=True))
            device_id = task.app_ui_device_id if task.app_ui_device else None

            execute_app_ui_batch(batch.id, script_ids, device_id)

            execution.log += f'APPUI batch {batch.id} completed\n'
            batch.refresh_from_db()
            if batch.status == 2:
                execution.status = TaskExecution.ExecutionStatus.SUCCESS
            else:
                execution.status = TaskExecution.ExecutionStatus.FAILED
            execution.finished_at = timezone.now()
            execution.log = '\n'.join(log_lines) + '\n' + execution.log
            execution.save()

            try:
                from notifications.services import send_task_notification
                send_task_notification(task, execution, batch)
            except Exception as push_err:
                logger.warning(f"推送通知失败: {push_err}")

            if task.schedule_type == ScheduledTask.ScheduleType.ONCE:
                task.status = ScheduledTask.TaskStatus.DISABLED
                task.save(update_fields=['status'])

            return {'status': execution.status, 'execution_id': execution.execution_id}
```

Add push integration to the success path for other modules. After the existing `execution.save()` (line ~138), add:

```python
        log_lines.append(f"[{timezone.now().isoformat()}] 任务执行完成")

        execution.status = TaskExecution.ExecutionStatus.SUCCESS
        execution.finished_at = timezone.now()
        execution.log = '\n'.join(log_lines)
        execution.save()

        try:
            from notifications.services import send_task_notification
            send_task_notification(task, execution, None)
        except Exception as push_err:
            logger.warning(f"推送通知失败: {push_err}")
```

Add push integration to the exception handler. After the `execution.save()` in the `except` block (after line ~155), add:

```python
        execution.status = TaskExecution.ExecutionStatus.FAILED
        execution.finished_at = timezone.now()
        execution.log = '\n'.join(log_lines)
        execution.error_message = str(e)
        execution.save()

        try:
            from notifications.services import send_task_notification
            send_task_notification(task, execution, None)
        except Exception as push_err:
            logger.warning(f"推送通知失败: {push_err}")
```

**3b. Add notifications menu mapping in `accounts/serializers.py`**

In `get_app_label_cn()`, add to the `app_labels` dict (after `"authtoken": "系统管理"`):

```python
            "authtoken": "系统管理",
            "notifications": "系统管理",
        }
```

In `get_app_label_en()`, add:

```python
            "authtoken": "System Settings",
            "notifications": "System Settings",
        }
```

In `get_app_label_subcategory()`, add to the system management subcategories dict:

```python
            "notifications": "推送配置",
        }
```

In `get_app_label_subcategory_en()`, add:

```python
            "notifications": "Push Config",
        }
```

In `get_app_label_subcategory_sort()`, add to the sort dict:

```python
            "任务调度": 29,
            "推送配置": 30,
        }
```

Also add model translations in `get_model_cn()` and `get_model_en()` for notifications models:

In `get_model_cn()` app_model_translations:
```python
                "notifications.webhookaddress": "推送地址",
                "notifications.messagetemplate": "消息模板",
```

In `get_model_en()` model_translations:
```python
            "notifications.webhookaddress": "Webhook Address",
            "notifications.messagetemplate": "Message Template",
```

**3c. Create system template data migration**

Create `WHartTest_Django/notifications/migrations/0002_initial_system_template.py`:

```python
from django.db import migrations


def create_system_template(apps, schema_editor):
    MessageTemplate = apps.get_model('notifications', 'MessageTemplate')
    User = apps.get_model('auth', 'User')

    # 使用超级管理员作为系统模板创建者，如果不存在则用 id=1 的用户
    creator = User.objects.filter(is_superuser=True).first()
    if not creator:
        creator = User.objects.first()

    if not creator:
        return  # 没有用户时跳过

    content = """## {{task_name}} 执行{{status}}

**项目**: {{project_name}}
**触发方式**: {{trigger_type}}
**执行人**: {{executor}}
**执行时间**: {{current_date}}
**执行时长**: {{duration}}

### 执行统计
- 用例总数: {{total}}
- 通过: {{passed}}
- 失败: {{failed}}
- 通过率: {{pass_rate}}

### 失败用例
{{failed_cases}}

[查看完整报告]({{report_url}})"""

    MessageTemplate.objects.get_or_create(
        name='默认任务通知模板',
        defaults={
            'content': content,
            'platform_type': 'feishu',
            'description': '系统内置的默认任务执行通知模板，包含任务信息和执行统计',
            'is_system': True,
            'creator': creator,
        },
    )


def remove_system_template(apps, schema_editor):
    MessageTemplate = apps.get_model('notifications', 'MessageTemplate')
    MessageTemplate.objects.filter(name='默认任务通知模板', is_system=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_system_template, remove_system_template),
    ]
```

- [ ] **Step 4: Run migrate and test to verify it passes**

```bash
cd WHartTest_Django && python manage.py migrate && python manage.py test notifications.SystemTemplateMigrationTest notifications.AccountsMenuMappingTest -v 2
```

Expected: All 3 tests pass.

- [ ] **Step 5: Run full notifications test suite to verify no regressions**

```bash
cd WHartTest_Django && python manage.py test notifications -v 2
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
cd WHartTest_Django && git add task_center/ accounts/ notifications/ && git commit -m "feat: integrate push notifications in tasks.py, add system template migration and menu mapping"
```

---

## Task 7: Frontend notifications service + types

**Files:**
- Create: `WHartTest_Vue/src/features/notifications/types/index.ts`
- Create: `WHartTest_Vue/src/features/notifications/services/notificationService.ts`

**Interfaces:**
- Produces: TypeScript types and API service functions for notifications
- Consumes: `request` from `@/utils/request`

- [ ] **Step 1: Create types**

Create `WHartTest_Vue/src/features/notifications/types/index.ts`:

```typescript
// 推送平台类型
export type PlatformType = 'feishu';

// 推送策略
export type PushConfig = 'always' | 'failure_only' | 'disabled';

// Webhook 地址
export interface WebhookAddress {
  id: number;
  name: string;
  url: string;
  platform_type: PlatformType;
  description: string;
  is_active: boolean;
  creator: number | null;
  created_at: string;
  updated_at: string;
}

// Webhook 地址精简版（普通用户可见）
export interface WebhookAddressLimited {
  id: number;
  name: string;
  is_active: boolean;
}

// Webhook 地址表单数据
export interface WebhookAddressFormData {
  name: string;
  url: string;
  platform_type?: PlatformType;
  description?: string;
  is_active?: boolean;
}

// 消息模板
export interface MessageTemplate {
  id: number;
  name: string;
  content: string;
  platform_type: PlatformType;
  description: string;
  is_system: boolean;
  creator: number | null;
  created_at: string;
  updated_at: string;
}

// 消息模板表单数据
export interface MessageTemplateFormData {
  name: string;
  content: string;
  platform_type?: PlatformType;
  description?: string;
}

// 变量定义
export interface NotificationVariable {
  name: string;
  description: string;
  example: string;
}

// 分页响应
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// 可用变量列表
export const NOTIFICATION_VARIABLES: NotificationVariable[] = [
  { name: 'task_name', description: '任务名称', example: '登录模块回归测试' },
  { name: 'project_name', description: '项目名称', example: 'J&T Express' },
  { name: 'status', description: '执行状态', example: '成功 / 失败' },
  { name: 'trigger_type', description: '触发方式', example: '定时 / 手动 / API' },
  { name: 'total', description: '用例总数', example: '15' },
  { name: 'passed', description: '通过数', example: '13' },
  { name: 'failed', description: '失败数', example: '2' },
  { name: 'pass_rate', description: '通过率', example: '86.7%' },
  { name: 'duration', description: '执行时长', example: '5分23秒' },
  { name: 'executor', description: '执行人', example: 'admin' },
  { name: 'failed_cases', description: '失败用例列表', example: 'test_login / test_payment' },
  { name: 'error_summary', description: '错误摘要', example: '2个用例执行失败' },
  { name: 'current_date', description: '当前日期时间', example: '2026-07-14 15:30:00' },
  { name: 'report_url', description: '报告链接', example: 'https://...' },
  { name: 'task_url', description: '任务详情链接', example: 'https://...' },
  { name: 'platform_name', description: '平台名称', example: 'WHartTest' },
];
```

- [ ] **Step 2: Create service**

Create `WHartTest_Vue/src/features/notifications/services/notificationService.ts`:

```typescript
import request from '@/utils/request';
import type {
  WebhookAddress,
  WebhookAddressLimited,
  WebhookAddressFormData,
  MessageTemplate,
  MessageTemplateFormData,
  PaginatedResponse,
} from '../types';

const BASE_URL = '/notifications';

// ==================== Webhook 地址管理 ====================

export async function getWebhookAddresses(): Promise<WebhookAddress[] | WebhookAddressLimited[]> {
  const response = await request.get(`${BASE_URL}/webhook-addresses/`);
  const data = response.data?.data || response.data;
  if (Array.isArray(data)) return data;
  return data?.results || [];
}

export async function createWebhookAddress(data: WebhookAddressFormData): Promise<WebhookAddress> {
  const response = await request.post(`${BASE_URL}/webhook-addresses/`, data);
  return response.data?.data || response.data;
}

export async function updateWebhookAddress(id: number, data: Partial<WebhookAddressFormData>): Promise<WebhookAddress> {
  const response = await request.patch(`${BASE_URL}/webhook-addresses/${id}/`, data);
  return response.data?.data || response.data;
}

export async function deleteWebhookAddress(id: number): Promise<void> {
  await request.delete(`${BASE_URL}/webhook-addresses/${id}/`);
}

export async function testWebhookAddress(id: number): Promise<{ message: string }> {
  const response = await request.post(`${BASE_URL}/webhook-addresses/${id}/test/`);
  return response.data?.data || response.data;
}

// ==================== 消息模板管理 ====================

export async function getMessageTemplates(): Promise<MessageTemplate[]> {
  const response = await request.get(`${BASE_URL}/message-templates/`);
  const data = response.data?.data || response.data;
  if (Array.isArray(data)) return data;
  return data?.results || [];
}

export async function createMessageTemplate(data: MessageTemplateFormData): Promise<MessageTemplate> {
  const response = await request.post(`${BASE_URL}/message-templates/`, data);
  return response.data?.data || response.data;
}

export async function updateMessageTemplate(id: number, data: Partial<MessageTemplateFormData>): Promise<MessageTemplate> {
  const response = await request.patch(`${BASE_URL}/message-templates/${id}/`, data);
  return response.data?.data || response.data;
}

export async function deleteMessageTemplate(id: number): Promise<void> {
  await request.delete(`${BASE_URL}/message-templates/${id}/`);
}
```

- [ ] **Step 3: Build to verify no errors**

```bash
cd WHartTest_Vue && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
cd WHartTest_Vue && git add src/features/notifications/ && git commit -m "feat: add notifications service and types"
```

---

## Task 8: Frontend WebhookAddress management page

**Files:**
- Create: `WHartTest_Vue/src/features/notifications/views/WebhookAddressView.vue`
- Create: `WHartTest_Vue/src/features/notifications/components/WebhookFormModal.vue`

**Interfaces:**
- Produces: WebhookAddressView page, WebhookFormModal component
- Consumes: notificationService, Arco Design components

- [ ] **Step 1: Create WebhookFormModal component**

Create `WHartTest_Vue/src/features/notifications/components/WebhookFormModal.vue`:

```vue
<template>
  <a-modal
    v-model:visible="visible"
    :title="isEditing ? '编辑推送地址' : '新增推送地址'"
    :width="520"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <template #footer>
      <a-space>
        <a-button @click="handleClose">取消</a-button>
        <a-button type="primary" :loading="submitting" @click="handleSubmit">保存</a-button>
      </a-space>
    </template>

    <a-form :model="form" layout="vertical" ref="formRef">
      <a-form-item label="地址名称" field="name" :rules="[{ required: true, message: '请输入地址名称' }]">
        <a-input v-model="form.name" placeholder="如：飞书测试群" :max-length="100" />
      </a-form-item>

      <a-form-item label="Webhook URL" field="url" :rules="[{ required: true, message: '请输入 Webhook URL' }]">
        <a-input v-model="form.url" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" />
      </a-form-item>

      <a-form-item label="描述" field="description">
        <a-textarea v-model="form.description" placeholder="可选描述" :auto-size="{ minRows: 2, maxRows: 4 }" />
      </a-form-item>

      <a-form-item label="启用状态" field="is_active">
        <a-switch v-model="form.is_active" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  createWebhookAddress,
  updateWebhookAddress,
  type WebhookAddress,
  type WebhookAddressFormData,
} from '../services/notificationService';

const visible = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref();

const defaultForm = (): WebhookAddressFormData => ({
  name: '',
  url: '',
  description: '',
  is_active: true,
});

const form = reactive<WebhookAddressFormData>(defaultForm());

const open = (addr?: WebhookAddress) => {
  Object.assign(form, defaultForm());
  if (addr) {
    isEditing.value = true;
    editingId.value = addr.id;
    form.name = addr.name;
    form.url = addr.url;
    form.description = addr.description || '';
    form.is_active = addr.is_active;
  } else {
    isEditing.value = false;
    editingId.value = null;
  }
  visible.value = true;
};

const handleClose = () => {
  visible.value = false;
};

const handleSubmit = async () => {
  const errors = await formRef.value?.validate();
  if (errors) return;

  submitting.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await updateWebhookAddress(editingId.value, { ...form });
      Message.success('推送地址已更新');
    } else {
      await createWebhookAddress({ ...form });
      Message.success('推送地址已创建');
    }
    visible.value = false;
    emit('success');
  } catch (error: any) {
    const msg = error?.response?.data?.detail || error?.error || '操作失败';
    Message.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  } finally {
    submitting.value = false;
  }
};

const emit = defineEmits<{ (e: 'success'): void }>();
defineExpose({ open });
</script>
```

- [ ] **Step 2: Create WebhookAddressView page**

Create `WHartTest_Vue/src/features/notifications/views/WebhookAddressView.vue`:

```vue
<template>
  <div class="webhook-address-view">
    <a-card title="推送地址管理">
      <template #extra>
        <a-button type="primary" @click="handleAdd">
          <template #icon><icon-plus /></template>
          新增地址
        </a-button>
      </template>

      <a-table
        :data="webhookList"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @page-change="onPageChange"
      >
        <template #columns>
          <a-table-column title="地址名称" data-index="name" />
          <a-table-column title="平台类型" data-index="platform_type">
            <template #cell="{ record }">
              <a-tag color="blue">{{ record.platform_type }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="URL" data-index="url">
            <template #cell="{ record }">
              <a-typography-text ellipsis style="max-width: 300px">
                {{ maskUrl(record.url) }}
              </a-typography-text>
            </template>
          </a-table-column>
          <a-table-column title="状态" data-index="is_active">
            <template #cell="{ record }">
              <a-tag :color="record.is_active ? 'green' : 'red'">
                {{ record.is_active ? '启用' : '停用' }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="描述" data-index="description" :ellipsis="true" />
          <a-table-column title="操作" :width="200">
            <template #cell="{ record }">
              <a-space>
                <a-button type="text" size="small" @click="handleEdit(record)">编辑</a-button>
                <a-button type="text" size="small" @click="handleTest(record)">测试推送</a-button>
                <a-popconfirm content="确定删除该地址？" @ok="handleDelete(record)">
                  <a-button type="text" status="danger" size="small">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>

    <WebhookFormModal ref="formModal" @success="loadData" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconPlus } from '@arco-design/web-vue/es/icon';
import {
  getWebhookAddresses,
  deleteWebhookAddress,
  testWebhookAddress,
  type WebhookAddress,
} from '../services/notificationService';
import WebhookFormModal from '../components/WebhookFormModal.vue';

const loading = ref(false);
const webhookList = ref<WebhookAddress[]>([]);
const formModal = ref<InstanceType<typeof WebhookFormModal>>();

const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
});

const maskUrl = (url: string) => {
  if (!url) return '';
  if (url.length <= 40) return url;
  return url.substring(0, 30) + '****' + url.substring(url.length - 10);
};

const loadData = async () => {
  loading.value = true;
  try {
    const data = await getWebhookAddresses();
    webhookList.value = data as WebhookAddress[];
    pagination.value.total = webhookList.value.length;
  } catch {
    webhookList.value = [];
  } finally {
    loading.value = false;
  }
};

const onPageChange = (page: number) => {
  pagination.value.current = page;
};

const handleAdd = () => {
  formModal.value?.open();
};

const handleEdit = (record: WebhookAddress) => {
  formModal.value?.open(record);
};

const handleDelete = async (record: WebhookAddress) => {
  try {
    await deleteWebhookAddress(record.id);
    Message.success('删除成功');
    loadData();
  } catch {
    Message.error('删除失败');
  }
};

const handleTest = async (record: WebhookAddress) => {
  try {
    Message.loading('正在发送测试消息...');
    const result = await testWebhookAddress(record.id);
    Message.success(result.message || '测试消息已发送');
  } catch {
    Message.error('测试推送失败');
  }
};

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.webhook-address-view {
  padding: 16px;
}
</style>
```

- [ ] **Step 3: Build to verify no errors**

```bash
cd WHartTest_Vue && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
cd WHartTest_Vue && git add src/features/notifications/ && git commit -m "feat: add webhook address management page and form modal"
```

---

## Task 9: Frontend MessageTemplate page + VariableHintPanel

**Files:**
- Create: `WHartTest_Vue/src/features/notifications/components/VariableHintPanel.vue`
- Create: `WHartTest_Vue/src/features/notifications/views/MessageTemplateView.vue`
- Create: `WHartTest_Vue/src/features/notifications/components/TemplateFormModal.vue`

**Interfaces:**
- Produces: VariableHintPanel (reusable), MessageTemplateView, TemplateFormModal
- Consumes: notificationService, NOTIFICATION_VARIABLES, Arco Design

- [ ] **Step 1: Create VariableHintPanel component**

Create `WHartTest_Vue/src/features/notifications/components/VariableHintPanel.vue`:

```vue
<template>
  <div class="variable-hint-panel">
    <a-collapse :default-active-key="[]">
      <a-collapse-item key="vars" header="变量参考">
        <div class="var-grid">
          <div
            v-for="v in variables"
            :key="v.name"
            class="var-item"
            @click="onVarClick(v)"
          >
            <a-tooltip :content="`点击插入 {{${v.name}}} - ${v.description}`">
              <a-tag color="arcoblue" style="cursor: pointer">
                {{ '{{' + v.name + '}}' }}
              </a-tag>
            </a-tooltip>
            <span class="var-desc">{{ v.description }}</span>
          </div>
        </div>
      </a-collapse-item>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { NOTIFICATION_VARIABLES, type NotificationVariable } from '../types';

const variables = NOTIFICATION_VARIABLES;

const emit = defineEmits<{
  (e: 'insert', varName: string): void;
}>();

const onVarClick = (v: NotificationVariable) => {
  emit('insert', v.name);
};
</script>

<style scoped>
.variable-hint-panel {
  margin-bottom: 8px;
}

.var-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.var-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.var-desc {
  font-size: 12px;
  color: var(--color-text-3);
}
</style>
```

- [ ] **Step 2: Create TemplateFormModal component**

Create `WHartTest_Vue/src/features/notifications/components/TemplateFormModal.vue`:

```vue
<template>
  <a-modal
    v-model:visible="visible"
    :title="isEditing ? '编辑模板' : '新增模板'"
    :width="800"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <template #footer>
      <a-space>
        <a-button @click="handleClose">取消</a-button>
        <a-button type="primary" :loading="submitting" @click="handleSubmit">保存</a-button>
      </a-space>
    </template>

    <a-form :model="form" layout="vertical" ref="formRef">
      <a-form-item label="模板名称" field="name" :rules="[{ required: true, message: '请输入模板名称' }]">
        <a-input v-model="form.name" placeholder="如：失败通知模板" :max-length="100" />
      </a-form-item>

      <a-form-item label="描述" field="description">
        <a-input v-model="form.description" placeholder="可选描述" />
      </a-form-item>

      <VariableHintPanel @insert="onInsertVariable" />

      <a-form-item label="模板内容" field="content" :rules="[{ required: true, message: '请输入模板内容' }]">
        <div class="content-editor">
          <a-textarea
            ref="contentRef"
            v-model="form.content"
            placeholder="支持 Markdown 和 {{变量}} 占位符"
            :auto-size="{ minRows: 8, maxRows: 20 }"
            style="font-family: monospace;"
          />
        </div>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  createMessageTemplate,
  updateMessageTemplate,
  type MessageTemplate,
  type MessageTemplateFormData,
} from '../services/notificationService';
import VariableHintPanel from './VariableHintPanel.vue';

const visible = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref();
const contentRef = ref();

const defaultForm = (): MessageTemplateFormData => ({
  name: '',
  content: '',
  description: '',
});

const form = reactive<MessageTemplateFormData>(defaultForm());

const open = (tpl?: MessageTemplate) => {
  Object.assign(form, defaultForm());
  if (tpl) {
    isEditing.value = true;
    editingId.value = tpl.id;
    form.name = tpl.name;
    form.content = tpl.content;
    form.description = tpl.description || '';
  } else {
    isEditing.value = false;
    editingId.value = null;
  }
  visible.value = true;
};

const handleClose = () => {
  visible.value = false;
};

const onInsertVariable = (varName: string) => {
  const insertion = `{{${varName}}}`;
  const textarea = contentRef.value?.$el?.querySelector('textarea');
  if (textarea) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    form.content = form.content.substring(0, start) + insertion + form.content.substring(end);
    nextTick(() => {
      textarea.focus();
      const newPos = start + insertion.length;
      textarea.setSelectionRange(newPos, newPos);
    });
  } else {
    form.content += insertion;
  }
};

const handleSubmit = async () => {
  const errors = await formRef.value?.validate();
  if (errors) return;

  submitting.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await updateMessageTemplate(editingId.value, { ...form });
      Message.success('模板已更新');
    } else {
      await createMessageTemplate({ ...form });
      Message.success('模板已创建');
    }
    visible.value = false;
    emit('success');
  } catch (error: any) {
    const msg = error?.response?.data?.detail || error?.error || '操作失败';
    Message.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  } finally {
    submitting.value = false;
  }
};

const emit = defineEmits<{ (e: 'success'): void }>();
defineExpose({ open });
</script>

<style scoped>
.content-editor {
  width: 100%;
}
</style>
```

- [ ] **Step 3: Create MessageTemplateView page**

Create `WHartTest_Vue/src/features/notifications/views/MessageTemplateView.vue`:

```vue
<template>
  <div class="message-template-view">
    <a-card title="消息模板库">
      <template #extra>
        <a-button type="primary" @click="handleAdd">
          <template #icon><icon-plus /></template>
          新增模板
        </a-button>
      </template>

      <a-table
        :data="templateList"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @page-change="onPageChange"
      >
        <template #columns>
          <a-table-column title="模板名称" data-index="name" />
          <a-table-column title="平台类型" data-index="platform_type">
            <template #cell="{ record }">
              <a-tag color="blue">{{ record.platform_type }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="类型" data-index="is_system">
            <template #cell="{ record }">
              <a-tag :color="record.is_system ? 'orangered' : 'cyan'">
                {{ record.is_system ? '系统内置' : '用户创建' }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="描述" data-index="description" :ellipsis="true" />
          <a-table-column title="创建人" data-index="creator">
            <template #cell="{ record }">
              {{ record.creator_name || record.creator || '-' }}
            </template>
          </a-table-column>
          <a-table-column title="更新时间" data-index="updated_at">
            <template #cell="{ record }">
              {{ formatDate(record.updated_at) }}
            </template>
          </a-table-column>
          <a-table-column title="操作" :width="150">
            <template #cell="{ record }">
              <a-space>
                <a-button type="text" size="small" @click="handleEdit(record)">编辑</a-button>
                <a-popconfirm
                  v-if="!record.is_system"
                  content="确定删除该模板？"
                  @ok="handleDelete(record)"
                >
                  <a-button type="text" status="danger" size="small">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>

    <TemplateFormModal ref="formModal" @success="loadData" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconPlus } from '@arco-design/web-vue/es/icon';
import {
  getMessageTemplates,
  deleteMessageTemplate,
  type MessageTemplate,
} from '../services/notificationService';
import TemplateFormModal from '../components/TemplateFormModal.vue';

const loading = ref(false);
const templateList = ref<MessageTemplate[]>([]);
const formModal = ref<InstanceType<typeof TemplateFormModal>>();

const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
});

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString('zh-CN');
};

const loadData = async () => {
  loading.value = true;
  try {
    const data = await getMessageTemplates();
    templateList.value = data;
    pagination.value.total = templateList.value.length;
  } catch {
    templateList.value = [];
  } finally {
    loading.value = false;
  }
};

const onPageChange = (page: number) => {
  pagination.value.current = page;
};

const handleAdd = () => {
  formModal.value?.open();
};

const handleEdit = (record: MessageTemplate) => {
  formModal.value?.open(record);
};

const handleDelete = async (record: MessageTemplate) => {
  try {
    await deleteMessageTemplate(record.id);
    Message.success('删除成功');
    loadData();
  } catch {
    Message.error('删除失败');
  }
};

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.message-template-view {
  padding: 16px;
}
</style>
```

- [ ] **Step 4: Build to verify no errors**

```bash
cd WHartTest_Vue && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
cd WHartTest_Vue && git add src/features/notifications/ && git commit -m "feat: add message template page, template form modal, and variable hint panel"
```

---

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
