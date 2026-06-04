# Generated for: add optional ui_environment FK to ScheduledTask (UI module use)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0001_initial'),
        ('task_center', '0005_scheduledtask_environment'),
    ]

    # 同样遵守 PG 「同一事务内不能先写 ui_environment_config 再 ALTER 引用它的表」的限制
    atomic = False

    operations = [
        migrations.AddField(
            model_name='scheduledtask',
            name='ui_environment',
            field=models.ForeignKey(
                help_text='UI 自动化模块执行时使用的浏览器/环境配置',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='scheduled_tasks',
                to='ui_automation.uienvironmentconfig',
                verbose_name='UI 环境配置',
                null=True,
                blank=True,
            ),
        ),
        # 保留为可空，仅在 UI 自动化模块下由序列化器强制必填
    ]
