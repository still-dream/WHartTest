"""更新系统模板：移除 report_url 链接，改为 report_hint 友好提示"""

from django.db import migrations


NEW_CONTENT = """## {{task_name}} 执行{{status}}

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

{{report_hint}}"""


def update_template(apps, schema_editor):
    MessageTemplate = apps.get_model('notifications', 'MessageTemplate')
    MessageTemplate.objects.filter(
        name='默认任务通知模板', is_system=True
    ).update(content=NEW_CONTENT)


def revert_template(apps, schema_editor):
    MessageTemplate = apps.get_model('notifications', 'MessageTemplate')
    old_content = """## {{task_name}} 执行{{status}}

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
    MessageTemplate.objects.filter(
        name='默认任务通知模板', is_system=True
    ).update(content=old_content)


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_initial_system_template'),
    ]

    operations = [
        migrations.RunPython(update_template, revert_template),
    ]
