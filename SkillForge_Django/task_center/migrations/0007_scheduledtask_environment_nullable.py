# Allow environment to be NULL for UI automation module tasks

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api_environments', '0001_initial'),
        ('task_center', '0006_scheduledtask_ui_environment'),
    ]

    # PG 限制：与引用表的 ALTER 不能与写操作放在同一事务；并且 0005 已经写入过数据
    atomic = False

    operations = [
        migrations.AlterField(
            model_name='scheduledtask',
            name='environment',
            field=models.ForeignKey(
                blank=True,
                help_text='测试套件模块执行时使用的 API 环境配置',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='scheduled_tasks',
                to='api_environments.apienvironment',
                verbose_name='API 环境配置',
            ),
        ),
    ]
