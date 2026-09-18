# Generated for: add required environment FK to ScheduledTask

from django.db import migrations, models
import django.db.models.deletion


def _assign_default_environment(apps, schema_editor):
    """为历史 ScheduledTask 数据兜底指派 environment。

    规则：
    1) 优先使用该项目下已有的任意一个环境；
    2) 若该项目下没有环境，则自动创建一个占位环境；
    3) 若系统中没有任何 ApiEnvironment（极端情况），则取一个全局任意一个环境。
    """
    ScheduledTask = apps.get_model('task_center', 'ScheduledTask')
    ApiEnvironment = apps.get_model('api_environments', 'ApiEnvironment')

    for task in ScheduledTask.objects.filter(environment__isnull=True):
        env = ApiEnvironment.objects.filter(project_id=task.project_id).first()
        if env is None:
            # 该项目下没有环境：自动创建一个占位环境，确保 NOT NULL 约束可通过
            # 使用 project_id 后缀避免 unique_together(name, project) 冲突
            placeholder_name = f'迁移占位环境-项目{task.project_id}'
            env, _created = ApiEnvironment.objects.get_or_create(
                project_id=task.project_id,
                name=placeholder_name,
                defaults={
                    'base_url': 'http://localhost',
                    'description': '由 0005 迁移自动创建的历史数据占位环境，请尽快指派正确环境',
                    'is_active': True,
                },
            )
        task.environment = env
        task.save(update_fields=['environment'])

    # 极端情况：系统中没有任何环境记录，任意拿一个即可
    pending = ScheduledTask.objects.filter(environment__isnull=True)
    if pending.exists():
        any_env = ApiEnvironment.objects.first()
        if any_env is not None:
            for task in pending:
                task.environment = any_env
                task.save(update_fields=['environment'])


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api_environments', '0001_initial'),
        ('task_center', '0004_remove_executing_status'),
    ]

    # PostgreSQL 限制：在同一事务内对 api_environments_apienvironment 写入
    # 后再 ALTER TABLE task_center_scheduledtask（其 FK 指向该表），会报
    # "cannot ALTER TABLE ... because it has pending trigger events"。
    # 因此将整个迁移拆成多个独立事务执行。
    atomic = False

    operations = [
        # 1) 先以可空方式添加字段
        migrations.AddField(
            model_name='scheduledtask',
            name='environment',
            field=models.ForeignKey(
                help_text='定时任务执行时使用的环境配置',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='scheduled_tasks',
                to='api_environments.apienvironment',
                verbose_name='环境配置',
                null=True,
            ),
        ),
        # 2) 数据迁移：单独事务，提交后再走下一步
        migrations.RunPython(
            code=_assign_default_environment,
            reverse_code=_noop_reverse,
        ),
        # 3) 单独事务：把字段改为 NOT NULL
        migrations.AlterField(
            model_name='scheduledtask',
            name='environment',
            field=models.ForeignKey(
                help_text='定时任务执行时使用的环境配置',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='scheduled_tasks',
                to='api_environments.apienvironment',
                verbose_name='环境配置',
            ),
        ),
    ]
