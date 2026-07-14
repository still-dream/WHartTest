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
