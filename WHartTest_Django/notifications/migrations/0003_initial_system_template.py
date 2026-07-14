from django.db import migrations
from django.contrib.auth.hashers import make_password


def create_system_template(apps, schema_editor):
    MessageTemplate = apps.get_model('notifications', 'MessageTemplate')
    User = apps.get_model('auth', 'User')

    # 使用超级管理员作为系统模板创建者，如果不存在则用 id=1 的用户
    creator = User.objects.filter(is_superuser=True).first()
    if not creator:
        creator = User.objects.first()

    if not creator:
        # 没有用户时创建系统用户作为模板创建者（不可登录）
        creator = User.objects.create(
            username='system',
            is_staff=True,
            is_superuser=True,
            password=make_password(None),
        )

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
