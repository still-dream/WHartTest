## Task 6: Push integration in tasks.py + system setup

**Files:**
- Modify: `WHartTest_Django/task_center/tasks.py`
- Modify: `WHartTest_Django/accounts/serializers.py`
- Create: `WHartTest_Django/notifications/migrations/0003_initial_system_template.py`
- Modify: `WHartTest_Django/notifications/tests.py`

**Interfaces:**
- Produces: push integration in Celery task, system template data migration, notifications menu mapping
- Consumes: `notifications.services.send_task_notification`, `notifications.models.MessageTemplate`

**IMPORTANT migration numbering:** The plan says `0002_initial_system_template.py` depending on `0001_initial`, but Task 2 already created `0002_messagetemplate`. So the data migration should be `0003_initial_system_template.py` with dependency on `('notifications', '0002_messagetemplate')`. Check existing migrations before creating.

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

Create `WHartTest_Django/notifications/migrations/0003_initial_system_template.py`:

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
        ('notifications', '0002_messagetemplate'),
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
