# APPUI 自动化功能模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an APPUI automation module based on Airtest, supporting .air script upload, device management, script execution with custom report generation, scheduled tasks, and online report viewing/download.

**Architecture:** New Django app `app_ui_automation` with Celery async execution. Hybrid execution engine: airtest Python library for script execution + AirtestIDE CLI reporter for report generation + pack_html() for standalone HTML. Integrates with existing `task_center` for scheduled tasks.

**Tech Stack:** Django 5.2, DRF, Celery, airtest Python library, AirtestIDE CLI (reporter only), Vue 3 + TypeScript frontend

## Global Constraints

- Django app name: `app_ui_automation`, registered in `INSTALLED_APPS`
- URL prefix: `api/app-ui-automation/`
- DB table naming: `app_ui_*` prefix (e.g., `app_ui_module`, `app_ui_script`)
- Follow existing `ui_automation` app patterns for serializers, views, URLs
- Report template: reuse `testcases/appuitest/log_template.html` and `run_all.py` pack_html()
- AirtestIDE path configured via `settings.AIRTEST_IDE_PATH`
- Multi-script scheduled execution must be serial (one after another)
- Docker deployment: AirtestIDE in same container, only for `reporter` command

---

## File Structure

### Backend (Django)

| File | Responsibility |
|------|---------------|
| `WHartTest_Django/app_ui_automation/__init__.py` | App init |
| `WHartTest_Django/app_ui_automation/apps.py` | AppConfig |
| `WHartTest_Django/app_ui_automation/models.py` | All data models |
| `WHartTest_Django/app_ui_automation/serializers.py` | DRF serializers |
| `WHartTest_Django/app_ui_automation/views.py` | DRF ViewSets |
| `WHartTest_Django/app_ui_automation/urls.py` | URL routing |
| `WHartTest_Django/app_ui_automation/executor.py` | Execution engine |
| `WHartTest_Django/app_ui_automation/tasks.py` | Celery async tasks |
| `WHartTest_Django/app_ui_automation/tests.py` | Unit tests |
| `WHartTest_Django/app_ui_automation/admin.py` | Django admin |
| `WHartTest_Django/app_ui_automation/migrations/` | DB migrations |

### Modified Files

| File | Change |
|------|--------|
| `WHartTest_Django/wharttest_django/settings.py` | Add app + Airtest config |
| `WHartTest_Django/wharttest_django/urls.py` | Add URL include |
| `WHartTest_Django/task_center/models.py` | Add TaskModule enum + FK fields |
| `WHartTest_Django/task_center/tasks.py` | Add APPUI execution branch |
| `WHartTest_Django/requirements.txt` | Add airtest dependency |
| `WHartTest_Vue/src/router/index.ts` | Add route |

### Frontend (Vue)

| File | Responsibility |
|------|---------------|
| `WHartTest_Vue/src/features/app-ui-automation/api/index.ts` | API service |
| `WHartTest_Vue/src/features/app-ui-automation/types/index.ts` | TypeScript types |
| `WHartTest_Vue/src/features/app-ui-automation/views/AppUiAutomationView.vue` | Main view |
| `WHartTest_Vue/src/features/app-ui-automation/views/ModuleTree.vue` | Module tree |
| `WHartTest_Vue/src/features/app-ui-automation/views/ScriptList.vue` | Script list + upload |
| `WHartTest_Vue/src/features/app-ui-automation/views/DeviceList.vue` | Device management |
| `WHartTest_Vue/src/features/app-ui-automation/views/ExecutionRecordList.vue` | Execution records |
| `WHartTest_Vue/src/features/app-ui-automation/views/BatchRecordList.vue` | Batch records |
| `WHartTest_Vue/src/features/app-ui-automation/index.ts` | Module exports |

---

## Task 1: Django App Scaffolding + AppUiModule Model

**Files:**
- Create: `WHartTest_Django/app_ui_automation/__init__.py`
- Create: `WHartTest_Django/app_ui_automation/apps.py`
- Create: `WHartTest_Django/app_ui_automation/models.py`
- Create: `WHartTest_Django/app_ui_automation/migrations/__init__.py`
- Create: `WHartTest_Django/app_ui_automation/tests.py`
- Modify: `WHartTest_Django/wharttest_django/settings.py`

**Interfaces:**
- Produces: `AppUiModule` model (project, name, parent, level, creator, created_at, updated_at)

- [ ] **Step 1: Create app directory structure**

Create files:
- `WHartTest_Django/app_ui_automation/__init__.py` (empty)
- `WHartTest_Django/app_ui_automation/migrations/__init__.py` (empty)

- [ ] **Step 2: Create apps.py**

```python
from django.apps import AppConfig


class AppUiAutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_ui_automation'
```

- [ ] **Step 3: Register app in settings.py**

Add `"app_ui_automation"` to `INSTALLED_APPS` in `WHartTest_Django/wharttest_django/settings.py` after `"ui_automation"`:

```python
    "ui_automation",  # UI 自动化应用。
    "app_ui_automation",  # APPUI 自动化应用（Airtest）。
```

- [ ] **Step 4: Write AppUiModule model**

In `WHartTest_Django/app_ui_automation/models.py`:

```python
# -*- coding: utf-8 -*-
"""APPUI 自动化数据模型"""

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from projects.models import Project


class AppUiModule(models.Model):
    """APPUI 自动化模块，支持5级子模块"""
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='app_ui_modules', verbose_name=_('所属项目')
    )
    name = models.CharField(_('模块名称'), max_length=100)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', verbose_name=_('父模块')
    )
    level = models.PositiveSmallIntegerField(_('模块级别'), default=1)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_app_ui_modules', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('APPUI 模块')
        verbose_name_plural = _('APPUI 模块')
        ordering = ['project', 'level', 'name']
        unique_together = ('project', 'parent', 'name')
        db_table = 'app_ui_module'

    def __str__(self):
        return f"{self.parent} > {self.name}" if self.parent else self.name

    def clean(self):
        if self.level > 5:
            raise ValidationError(_('模块级别不能超过5级'))
        if self.parent and self.parent.project_id != self.project_id:
            raise ValidationError(_('父模块必须属于同一个项目'))
        self.level = (self.parent.level + 1) if self.parent else 1

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
```

- [ ] **Step 5: Write tests**

In `WHartTest_Django/app_ui_automation/tests.py`:

```python
from django.test import TestCase
from django.contrib.auth.models import User
from projects.models import Project
from app_ui_automation.models import AppUiModule


class AppUiModuleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_root_module(self):
        module = AppUiModule.objects.create(
            project=self.project, name='Root Module', creator=self.user
        )
        self.assertEqual(module.level, 1)
        self.assertIsNone(module.parent)

    def test_create_child_module(self):
        parent = AppUiModule.objects.create(
            project=self.project, name='Parent', creator=self.user
        )
        child = AppUiModule.objects.create(
            project=self.project, name='Child', parent=parent, creator=self.user
        )
        self.assertEqual(child.level, 2)

    def test_module_level_max_5(self):
        parent = AppUiModule.objects.create(
            project=self.project, name='L1', creator=self.user
        )
        for i in range(3):
            parent = AppUiModule.objects.create(
                project=self.project, name=f'L{i+2}', parent=parent, creator=self.user
            )
        self.assertEqual(parent.level, 5)
```

- [ ] **Step 6: Run migration and test**

```bash
cd WHartTest_Django
python manage.py makemigrations app_ui_automation
python manage.py migrate
python manage.py test app_ui_automation.tests.AppUiModuleModelTest
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add WHartTest_Django/app_ui_automation/
git add WHartTest_Django/wharttest_django/settings.py
git commit -m "feat: scaffold app_ui_automation Django app with AppUiModule model"
```

---

## Task 2: AppUiScript Model + Upload Logic

**Files:**
- Modify: `WHartTest_Django/app_ui_automation/models.py`
- Modify: `WHartTest_Django/app_ui_automation/tests.py`

**Interfaces:**
- Consumes: `AppUiModule` from Task 1
- Produces: `AppUiScript` model with `script_file`, `script_dir`, `script_entry` fields; `app_ui_script_path()` function

- [ ] **Step 1: Add AppUiScript model**

Append to `WHartTest_Django/app_ui_automation/models.py` (add `import os` and `from django.conf import settings` to imports):

```python
import os
from django.conf import settings


def app_ui_script_path(instance, filename):
    """脚本文件存储路径: app_ui_scripts/{project_id}/{script_id}/"""
    return f"app_ui_scripts/{instance.project.id}/{instance.id}/{filename}"


class AppUiScript(models.Model):
    """APPUI Airtest 脚本"""
    PLATFORM_CHOICES = [('android', _('Android')), ('ios', _('iOS'))]
    STATUS_CHOICES = [
        ('idle', _('空闲')), ('running', _('执行中')),
        ('success', _('成功')), ('failed', _('失败')),
    ]
    LEVEL_CHOICES = [('P0', 'P0'), ('P1', 'P1'), ('P2', 'P2'), ('P3', 'P3')]

    project = models.ForeignKey(Project, on_delete=models.CASCADE,
        related_name='app_ui_scripts', verbose_name=_('所属项目'))
    module = models.ForeignKey(AppUiModule, on_delete=models.PROTECT,
        related_name='scripts', verbose_name=_('所属模块'))
    name = models.CharField(_('脚本名称'), max_length=255)
    description = models.TextField(_('脚本描述'), blank=True, null=True)
    platform = models.CharField(_('目标平台'), max_length=10,
        choices=PLATFORM_CHOICES, default='android')
    script_file = models.FileField(_('Airtest脚本包'), upload_to=app_ui_script_path,
        help_text=_('上传 .air 目录打包的 zip 文件'))
    script_dir = models.CharField(_('脚本目录路径'), max_length=500, blank=True, default='')
    script_entry = models.CharField(_('脚本入口文件'), max_length=255, blank=True, default='')
    level = models.CharField(_('用例等级'), max_length=2, choices=LEVEL_CHOICES, default='P2')
    status = models.CharField(_('最近状态'), max_length=10, choices=STATUS_CHOICES, default='idle')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='created_app_ui_scripts', verbose_name=_('创建人'))
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('APPUI 脚本')
        verbose_name_plural = _('APPUI 脚本')
        ordering = ['-created_at']
        db_table = 'app_ui_script'

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    def delete(self, *args, **kwargs):
        if self.script_file:
            path = self.script_file.path
            if os.path.isfile(path):
                os.remove(path)
        if self.script_dir:
            import shutil
            full_dir = os.path.join(settings.MEDIA_ROOT, self.script_dir)
            if os.path.isdir(full_dir):
                shutil.rmtree(full_dir, ignore_errors=True)
        super().delete(*args, **kwargs)
```

- [ ] **Step 2: Write tests**

Append to `WHartTest_Django/app_ui_automation/tests.py`:

```python
import io
import zipfile
from django.core.files.uploadedfile import SimpleUploadedFile
from app_ui_automation.models import AppUiScript


class AppUiScriptModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.module = AppUiModule.objects.create(
            project=self.project, name='Test Module', creator=self.user
        )

    def _make_air_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('test.air/test.py',
                '# -*- encoding=utf8 -*-\nfrom airtest.core.api import *\nauto_setup(__file__)\n')
            zf.writestr('test.air/tpl123.png', b'fake_png_data')
        buf.seek(0)
        return SimpleUploadedFile('test.air.zip', buf.read(), content_type='application/zip')

    def test_create_script(self):
        script = AppUiScript.objects.create(
            project=self.project, module=self.module, name='Test Script',
            platform='android', script_file=self._make_air_zip(), creator=self.user
        )
        self.assertEqual(script.name, 'Test Script')
        self.assertEqual(script.status, 'idle')
        self.assertTrue(script.script_file.name.startswith('app_ui_scripts/'))
```

- [ ] **Step 3: Run migration and test**

```bash
cd WHartTest_Django
python manage.py makemigrations app_ui_automation
python manage.py migrate
python manage.py test app_ui_automation.tests.AppUiScriptModelTest
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add WHartTest_Django/app_ui_automation/
git commit -m "feat: add AppUiScript model with .air zip upload support"
```

---

## Task 3: AppUiDevice Model

**Files:**
- Modify: `WHartTest_Django/app_ui_automation/models.py`
- Modify: `WHartTest_Django/app_ui_automation/tests.py`

**Interfaces:**
- Produces: `AppUiDevice` model (connection_type, device_uri, status)

- [ ] **Step 1: Add AppUiDevice model**

Append to `WHartTest_Django/app_ui_automation/models.py`:

```python
class AppUiDevice(models.Model):
    """APPUI 测试设备管理"""
    CONNECTION_TYPE_CHOICES = [
        ('adb_tcp', _('ADB TCP 远程')),
        ('emulator', _('Android 模拟器')),
        ('cloud', _('云真机平台')),
        ('usb', _('USB 直连')),
    ]
    PLATFORM_CHOICES = [('android', _('Android')), ('ios', _('iOS'))]
    STATUS_CHOICES = [('online', _('在线')), ('offline', _('离线')), ('busy', _('忙碌'))]

    project = models.ForeignKey(Project, on_delete=models.CASCADE,
        related_name='app_ui_devices', verbose_name=_('所属项目'))
    name = models.CharField(_('设备名称'), max_length=100, help_text=_('如：测试机-小米12'))
    connection_type = models.CharField(_('连接类型'), max_length=20,
        choices=CONNECTION_TYPE_CHOICES, default='adb_tcp')
    platform = models.CharField(_('平台'), max_length=10,
        choices=PLATFORM_CHOICES, default='android')
    device_uri = models.CharField(_('设备连接URI'), max_length=500,
        help_text=_('Android: android://127.0.0.1:5037/序列号; iOS: ios:///127.0.0.1:8100'))
    device_serial = models.CharField(_('设备序列号'), max_length=255, blank=True, default='')
    status = models.CharField(_('设备状态'), max_length=10,
        choices=STATUS_CHOICES, default='offline')
    description = models.TextField(_('设备描述'), blank=True, null=True)
    is_default = models.BooleanField(_('是否默认'), default=False)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='created_app_ui_devices', verbose_name=_('创建人'))
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('APPUI 设备')
        verbose_name_plural = _('APPUI 设备')
        ordering = ['project', 'name']
        unique_together = ('project', 'name')
        db_table = 'app_ui_device'

    def __str__(self):
        return f"{self.project.name} - {self.name}"
```

- [ ] **Step 2: Write tests**

Append to `WHartTest_Django/app_ui_automation/tests.py`:

```python
from app_ui_automation.models import AppUiDevice


class AppUiDeviceModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_device(self):
        device = AppUiDevice.objects.create(
            project=self.project, name='小米12',
            connection_type='adb_tcp', platform='android',
            device_uri='android://127.0.0.1:5037/118f492e',
            device_serial='118f492e', creator=self.user
        )
        self.assertEqual(device.status, 'offline')
        self.assertFalse(device.is_default)
```

- [ ] **Step 3: Run migration and test**

```bash
cd WHartTest_Django
python manage.py makemigrations app_ui_automation
python manage.py migrate
python manage.py test app_ui_automation.tests.AppUiDeviceModelTest
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add WHartTest_Django/app_ui_automation/
git commit -m "feat: add AppUiDevice model with multi-connection-type support"
```

---

## Task 4: Execution Record + Batch Record Models

**Files:**
- Modify: `WHartTest_Django/app_ui_automation/models.py`
- Modify: `WHartTest_Django/app_ui_automation/tests.py`

**Interfaces:**
- Consumes: `AppUiScript` (Task 2), `AppUiDevice` (Task 3)
- Produces: `AppUiExecutionRecord`, `AppUiBatchExecutionRecord` models

- [ ] **Step 1: Add batch + execution record models**

Append to `WHartTest_Django/app_ui_automation/models.py`:

```python
class AppUiBatchExecutionRecord(models.Model):
    """APPUI 批量执行记录"""
    STATUS_CHOICES = [
        (0, _('待执行')), (1, _('执行中')),
        (2, _('全部成功')), (3, _('部分失败')), (4, _('全部失败')),
    ]
    TRIGGER_TYPE_CHOICES = [('manual', _('手动')), ('scheduled', _('定时')), ('api', _('API'))]

    name = models.CharField(_('批次名称'), max_length=255)
    total_scripts = models.IntegerField(_('脚本总数'), default=0)
    passed_scripts = models.IntegerField(_('成功数'), default=0)
    failed_scripts = models.IntegerField(_('失败数'), default=0)
    status = models.SmallIntegerField(_('状态'), choices=STATUS_CHOICES, default=0)
    trigger_type = models.CharField(_('触发类型'), max_length=20,
        choices=TRIGGER_TYPE_CHOICES, default='manual')
    executor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='app_ui_batch_executions', verbose_name=_('执行人'))
    start_time = models.DateTimeField(_('开始时间'), null=True, blank=True)
    end_time = models.DateTimeField(_('结束时间'), null=True, blank=True)
    duration = models.FloatField(_('总时长（秒）'), null=True, blank=True)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('APPUI 批量执行记录')
        verbose_name_plural = _('APPUI 批量执行记录')
        ordering = ['-created_at']
        db_table = 'app_ui_batch_execution_record'

    def __str__(self):
        return f"{self.name} ({self.passed_scripts}/{self.total_scripts})"

    def update_statistics(self):
        records = self.execution_records.all()
        self.passed_scripts = records.filter(status=2).count()
        self.failed_scripts = records.filter(status=3).count()
        completed = self.passed_scripts + self.failed_scripts
        if completed >= self.total_scripts:
            if self.failed_scripts == 0:
                self.status = 2
            elif self.passed_scripts == 0:
                self.status = 4
            else:
                self.status = 3
            from django.utils import timezone
            self.end_time = timezone.now()
            if self.start_time:
                self.duration = (self.end_time - self.start_time).total_seconds()
        self.save()


class AppUiExecutionRecord(models.Model):
    """APPUI 脚本执行记录"""
    STATUS_CHOICES = [(0, _('等待中')), (1, _('执行中')), (2, _('成功')), (3, _('失败')), (4, _('取消'))]
    TRIGGER_TYPE_CHOICES = [('manual', _('手动')), ('scheduled', _('定时')), ('api', _('API')), ('debug', _('调试'))]

    batch = models.ForeignKey(AppUiBatchExecutionRecord, on_delete=models.CASCADE,
        null=True, blank=True, related_name='execution_records', verbose_name=_('所属批次'))
    script = models.ForeignKey(AppUiScript, on_delete=models.CASCADE,
        related_name='execution_records', verbose_name=_('执行脚本'))
    device = models.ForeignKey(AppUiDevice, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='execution_records', verbose_name=_('执行设备'))
    status = models.SmallIntegerField(_('执行状态'), choices=STATUS_CHOICES, default=0)
    trigger_type = models.CharField(_('触发类型'), max_length=20,
        choices=TRIGGER_TYPE_CHOICES, default='manual')
    executor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='app_ui_executions', verbose_name=_('执行人'))
    total_steps = models.IntegerField(_('总步骤数'), default=0)
    passed_steps = models.IntegerField(_('通过步骤数'), default=0)
    failed_steps = models.IntegerField(_('失败步骤数'), default=0)
    report_path = models.CharField(_('报告文件路径'), max_length=500, blank=True, default='')
    log_dir = models.CharField(_('日志目录路径'), max_length=500, blank=True, default='')
    execution_log = models.TextField(_('执行日志'), blank=True, null=True)
    error_message = models.TextField(_('错误信息'), null=True, blank=True)
    start_time = models.DateTimeField(_('开始时间'), null=True, blank=True)
    end_time = models.DateTimeField(_('结束时间'), null=True, blank=True)
    duration = models.FloatField(_('执行时长（秒）'), null=True, blank=True)
    celery_task_id = models.CharField(_('Celery任务ID'), max_length=255, blank=True, default='')
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('APPUI 执行记录')
        verbose_name_plural = _('APPUI 执行记录')
        ordering = ['-created_at']
        db_table = 'app_ui_execution_record'

    def __str__(self):
        return f"{self.script.name} - {self.get_status_display()}"
```

- [ ] **Step 2: Write tests**

Append to `WHartTest_Django/app_ui_automation/tests.py`:

```python
from app_ui_automation.models import AppUiExecutionRecord, AppUiBatchExecutionRecord


class AppUiExecutionRecordModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.module = AppUiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.script = AppUiScript.objects.create(
            project=self.project, module=self.module, name='S',
            script_file=SimpleUploadedFile('t.zip', b'fake', content_type='application/zip'),
            creator=self.user
        )

    def test_create_execution_record(self):
        record = AppUiExecutionRecord.objects.create(
            script=self.script, trigger_type='debug', executor=self.user
        )
        self.assertEqual(record.status, 0)

    def test_batch_update_statistics(self):
        batch = AppUiBatchExecutionRecord.objects.create(name='B', total_scripts=2, executor=self.user)
        AppUiExecutionRecord.objects.create(batch=batch, script=self.script, status=2)
        AppUiExecutionRecord.objects.create(batch=batch, script=self.script, status=3)
        batch.update_statistics()
        self.assertEqual(batch.passed_scripts, 1)
        self.assertEqual(batch.failed_scripts, 1)
        self.assertEqual(batch.status, 3)
```

- [ ] **Step 3: Run migration and test**

```bash
cd WHartTest_Django
python manage.py makemigrations app_ui_automation
python manage.py migrate
python manage.py test app_ui_automation.tests.AppUiExecutionRecordModelTest
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add WHartTest_Django/app_ui_automation/
git commit -m "feat: add AppUiExecutionRecord and AppUiBatchExecutionRecord models"
```

---

## Task 5: Serializers + ViewSets + URLs

**Files:**
- Create: `WHartTest_Django/app_ui_automation/serializers.py`
- Create: `WHartTest_Django/app_ui_automation/views.py`
- Create: `WHartTest_Django/app_ui_automation/urls.py`
- Create: `WHartTest_Django/app_ui_automation/admin.py`
- Modify: `WHartTest_Django/wharttest_django/urls.py`

**Interfaces:**
- Consumes: All models from Tasks 1-4, `execute_app_ui_script` task from Task 7
- Produces: REST API at `api/app-ui-automation/`

**Note:** This task depends on Task 7 (tasks.py). Create a stub `tasks.py` first if implementing in order.

- [ ] **Step 1: Create serializers.py**

Full code for `WHartTest_Django/app_ui_automation/serializers.py` - see design spec section 4.2 for serializer field definitions. Follow `ui_automation/serializers.py` patterns.

- [ ] **Step 2: Create views.py**

Full code for `WHartTest_Django/app_ui_automation/views.py` - includes:
- `AppUiModuleViewSet` (CRUD + tree action, follows `UiModuleViewSet`)
- `AppUiScriptViewSet` (CRUD + preview/execute actions, includes `_extract_and_parse()` method)
- `AppUiDeviceViewSet` (CRUD + check action)
- `AppUiExecutionRecordViewSet` (ReadOnly + report/download/cancel actions)
- `AppUiBatchExecutionRecordViewSet` (ReadOnly)

See design spec section 4.3 for complete view code.

- [ ] **Step 3: Create urls.py**

```python
# -*- coding: utf-8 -*-
from rest_framework.routers import DefaultRouter
from .views import (
    AppUiModuleViewSet, AppUiScriptViewSet, AppUiDeviceViewSet,
    AppUiExecutionRecordViewSet, AppUiBatchExecutionRecordViewSet
)

router = DefaultRouter()
router.register('modules', AppUiModuleViewSet, basename='app-ui-modules')
router.register('scripts', AppUiScriptViewSet, basename='app-ui-scripts')
router.register('devices', AppUiDeviceViewSet, basename='app-ui-devices')
router.register('execution-records', AppUiExecutionRecordViewSet, basename='app-ui-execution-records')
router.register('batch-records', AppUiBatchExecutionRecordViewSet, basename='app-ui-batch-records')

urlpatterns = router.urls
```

- [ ] **Step 4: Create admin.py**

```python
from django.contrib import admin
from .models import (AppUiModule, AppUiScript, AppUiDevice,
    AppUiExecutionRecord, AppUiBatchExecutionRecord)

admin.site.register(AppUiModule)
admin.site.register(AppUiScript)
admin.site.register(AppUiDevice)
admin.site.register(AppUiExecutionRecord)
admin.site.register(AppUiBatchExecutionRecord)
```

- [ ] **Step 5: Register URLs in main urls.py**

In `WHartTest_Django/wharttest_django/urls.py`, add after the ui-automation include:

```python
    path("api/app-ui-automation/", include("app_ui_automation.urls")),
```

- [ ] **Step 6: Run server and verify**

```bash
cd WHartTest_Django
python manage.py runserver
curl http://localhost:8000/api/app-ui-automation/modules/
```

Expected: 200 OK

- [ ] **Step 7: Commit**

```bash
git add WHartTest_Django/app_ui_automation/
git add WHartTest_Django/wharttest_django/urls.py
git commit -m "feat: add serializers, views, URLs for app_ui_automation API"
```

---

## Task 6: Execution Engine (executor.py)

**Files:**
- Create: `WHartTest_Django/app_ui_automation/executor.py`

**Interfaces:**
- Consumes: `AppUiScript`, `AppUiDevice`, `AppUiExecutionRecord` models; `run_all.py` `pack_html()` function
- Produces: `AppUiScriptExecutor` class with `execute(execution_record_id)` method

- [ ] **Step 1: Create executor.py**

Create `WHartTest_Django/app_ui_automation/executor.py` with the `AppUiScriptExecutor` class implementing the three-step pipeline:

1. `_run_script_with_airtest()` - uses `from airtest.core.api import connect_device, set_logdir` then `exec()` the script with `__file__` set correctly for Template image paths
2. `_generate_report()` - calls `subprocess.run([AIRTEST_IDE_PATH, "reporter", ...])` then `_apply_custom_template()` to inject CSS from `log_template.html`
3. `_pack_html()` - imports `pack_html` from `testcases/appuitest/log_untitled/run_all.py` and calls it
4. `_parse_log_stats()` - parses JSON-lines `log.txt`, counting `depth==1` entries with operation names (`touch`, `swipe`, `assert_exists`, etc.)

See design spec section 5 for complete code.

- [ ] **Step 2: Verify import**

```bash
cd WHartTest_Django
python -c "from app_ui_automation.executor import AppUiScriptExecutor; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add WHartTest_Django/app_ui_automation/executor.py
git commit -m "feat: add execution engine with airtest+reporter+pack_html pipeline"
```

---

## Task 7: Celery Tasks

**Files:**
- Create: `WHartTest_Django/app_ui_automation/tasks.py`

**Interfaces:**
- Consumes: `AppUiScriptExecutor` from Task 6
- Produces: `execute_app_ui_script(execution_record_id)` and `execute_app_ui_batch(batch_record_id, script_ids, device_id)` Celery tasks

- [ ] **Step 1: Create tasks.py**

```python
# -*- coding: utf-8 -*-
"""APPUI 自动化 Celery 异步任务"""

import logging
from celery import shared_task
from django.utils import timezone

from .models import AppUiExecutionRecord, AppUiBatchExecutionRecord, AppUiScript
from .executor import AppUiScriptExecutor

logger = logging.getLogger(__name__)


@shared_task
def execute_app_ui_script(execution_record_id):
    """执行单个 APPUI 脚本"""
    logger.info(f"开始执行 APPUI 脚本, record_id={execution_record_id}")
    executor = AppUiScriptExecutor()
    executor.execute(execution_record_id)


@shared_task
def execute_app_ui_batch(batch_record_id, script_ids, device_id=None):
    """串行执行多个脚本（定时任务）"""
    logger.info(f"批量执行, batch_id={batch_record_id}, scripts={script_ids}")
    batch = AppUiBatchExecutionRecord.objects.get(id=batch_record_id)
    batch.status = 1
    batch.start_time = timezone.now()
    batch.save()

    executor = AppUiScriptExecutor()
    for script_id in script_ids:
        try:
            record = AppUiExecutionRecord.objects.create(
                batch=batch, script_id=script_id, device_id=device_id,
                trigger_type='scheduled', status=0,
            )
            executor.execute(record.id)
        except Exception as e:
            logger.error(f"脚本执行失败, script_id={script_id}: {e}")
            AppUiExecutionRecord.objects.create(
                batch=batch, script_id=script_id, device_id=device_id,
                trigger_type='scheduled', status=3, error_message=str(e),
                start_time=timezone.now(), end_time=timezone.now(),
            )
    batch.update_statistics()
```

- [ ] **Step 2: Verify import**

```bash
cd WHartTest_Django
python -c "from app_ui_automation.tasks import execute_app_ui_script; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add WHartTest_Django/app_ui_automation/tasks.py
git commit -m "feat: add Celery tasks for script and batch execution"
```

---

## Task 8: Settings + Dependencies

**Files:**
- Modify: `WHartTest_Django/wharttest_django/settings.py`
- Modify: `WHartTest_Django/requirements.txt`

- [ ] **Step 1: Add Airtest config to settings.py**

Append to `WHartTest_Django/wharttest_django/settings.py`:

```python
# AirtestIDE 配置（仅用于报告生成）
AIRTEST_IDE_PATH = os.environ.get('AIRTEST_IDE_PATH',
    r'C:\Program Files\AirtestIDE-win-1.2.17\AirtestIDE\AirtestIDE')
AIRTEST_REPORT_LANG = 'zh'
AIRTEST_REPORT_TEMPLATE = os.path.join(BASE_DIR, 'testcases', 'appuitest', 'log_template.html')
```

- [ ] **Step 2: Add airtest to requirements.txt**

Append to `WHartTest_Django/requirements.txt`:
```
airtest>=1.3.0
```

- [ ] **Step 3: Install**

```bash
cd WHartTest_Django
pip install airtest>=1.3.0
```

- [ ] **Step 4: Commit**

```bash
git add WHartTest_Django/wharttest_django/settings.py WHartTest_Django/requirements.txt
git commit -m "feat: add Airtest configuration and dependency"
```

---

## Task 9: task_center Integration

**Files:**
- Modify: `WHartTest_Django/task_center/models.py`
- Modify: `WHartTest_Django/task_center/tasks.py`

- [ ] **Step 1: Extend ScheduledTask model**

In `WHartTest_Django/task_center/models.py`:

1. Add `APP_UI_AUTOMATION = 'app_ui_automation', _('APPUI 自动化')` to `TaskModule`
2. Add `app_ui_scripts` M2M field and `app_ui_device` FK field to `ScheduledTask`

- [ ] **Step 2: Create migration**

```bash
cd WHartTest_Django
python manage.py makemigrations task_center
python manage.py migrate
```

- [ ] **Step 3: Add APPUI branch in task_center/tasks.py**

In `execute_scheduled_task`, add:
```python
if task.module == ScheduledTask.TaskModule.APP_UI_AUTOMATION:
    from app_ui_automation.models import AppUiBatchExecutionRecord
    from app_ui_automation.tasks import execute_app_ui_batch
    scripts = task.app_ui_scripts.all()
    batch = AppUiBatchExecutionRecord.objects.create(
        name=f"定时任务-{task.name}", total_scripts=scripts.count(),
        trigger_type='scheduled', executor=task.creator, start_time=timezone.now(),
    )
    execute_app_ui_batch(batch.id, list(scripts.values_list('id', flat=True)),
                         task.app_ui_device_id)
```

- [ ] **Step 4: Commit**

```bash
git add WHartTest_Django/task_center/
git commit -m "feat: integrate APPUI automation into task_center scheduled tasks"
```

---

## Task 10: Frontend - API + Types + Router

**Files:**
- Create: `WHartTest_Vue/src/features/app-ui-automation/api/index.ts`
- Create: `WHartTest_Vue/src/features/app-ui-automation/types/index.ts`
- Create: `WHartTest_Vue/src/features/app-ui-automation/index.ts`
- Modify: `WHartTest_Vue/src/router/index.ts`

- [ ] **Step 1: Create types/index.ts**

Define TypeScript interfaces for `AppUiModule`, `AppUiScript`, `AppUiDevice`, `AppUiExecutionRecord`, `AppUiBatchExecutionRecord`, `PaginatedResponse<T>`. See design spec section 7 for field details.

- [ ] **Step 2: Create api/index.ts**

Create API service objects: `moduleApi`, `scriptApi`, `deviceApi`, `executionRecordApi`, `batchRecordApi`. Follow the pattern from `ui-automation/api/index.ts`. Base URL: `/app-ui-automation`.

- [ ] **Step 3: Create index.ts**

```typescript
export * from './types'
export * from './api'
export { default as AppUiAutomationView } from './views/AppUiAutomationView.vue'
```

- [ ] **Step 4: Add route in router/index.ts**

In `WHartTest_Vue/src/router/index.ts`:

```typescript
import AppUiAutomationView from '@/features/app-ui-automation/views/AppUiAutomationView.vue'

// Add to children array:
{
  path: 'app-ui-automation',
  name: 'AppUiAutomation',
  component: AppUiAutomationView,
},
```

- [ ] **Step 5: Commit**

```bash
git add WHartTest_Vue/src/features/app-ui-automation/
git add WHartTest_Vue/src/router/index.ts
git commit -m "feat: add frontend API service, types, and router for app-ui-automation"
```

---

## Task 11: Frontend - Views

**Files:**
- Create: `WHartTest_Vue/src/features/app-ui-automation/views/AppUiAutomationView.vue`
- Create: `WHartTest_Vue/src/features/app-ui-automation/views/ModuleTree.vue`
- Create: `WHartTest_Vue/src/features/app-ui-automation/views/ScriptList.vue`
- Create: `WHartTest_Vue/src/features/app-ui-automation/views/DeviceList.vue`
- Create: `WHartTest_Vue/src/features/app-ui-automation/views/ExecutionRecordList.vue`
- Create: `WHartTest_Vue/src/features/app-ui-automation/views/BatchRecordList.vue`

- [ ] **Step 1: Create AppUiAutomationView.vue**

Main view with `el-container` layout: left aside (ModuleTree) + main area (el-tabs with 4 panes: scripts, devices, records, batches). Follow `UiAutomationView.vue` pattern.

- [ ] **Step 2: Create ModuleTree.vue**

el-tree component loading from `moduleApi.tree(projectId)`. Emit `select` event with module ID on node click. Include "全部" root option.

- [ ] **Step 3: Create ScriptList.vue**

el-table with columns: name, platform, level, status, actions (execute, preview, delete). Upload button opens dialog with el-upload for zip file. Execute button opens dialog to select device, then calls `scriptApi.execute()`.

- [ ] **Step 4: Create DeviceList.vue**

el-table with columns: name, connection_type, platform, device_uri, status, actions (check, edit, delete). Add device button opens form dialog.

- [ ] **Step 5: Create ExecutionRecordList.vue**

el-table with columns: script_name, status, trigger_type, steps (passed/total), duration, created_at, actions. When status=1 (running), poll every 3 seconds. Actions: "查看报告" (opens `executionRecordApi.reportUrl(id)` in new tab), "下载" (triggers download from `executionRecordApi.downloadUrl(id)`), "取消" (when running).

- [ ] **Step 6: Create BatchRecordList.vue**

el-table with columns: name, total_scripts, passed/failed, status, trigger_type, duration, created_at. Expandable row showing individual execution records.

- [ ] **Step 7: Commit**

```bash
git add WHartTest_Vue/src/features/app-ui-automation/views/
git commit -m "feat: add frontend views for app-ui-automation module"
```
