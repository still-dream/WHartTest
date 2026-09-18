# -*- coding: utf-8 -*-
"""注册 APK 自动清理定时任务到 django-celery-beat（每天凌晨 3 点执行）"""

from django.db import migrations


CLEANUP_TASK_NAME = 'app_ui_automation.cleanup_apks_daily'
CLEANUP_TASK_DESCRIPTION = '每天凌晨清理 30 天前上传的过期 APP 安装包'


def register_periodic_task(apps, schema_editor):
    """注册定时任务到 django-celery-beat"""
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')

    # 每天凌晨 3:00 执行
    # 注意：django-celery-beat 2.6+ 已移除 CrontabSchedule.timezone 字段，
    # 时区由全局 CELERY_TIMEZONE 配置统一控制。
    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute='0',
        hour='3',
        day_of_week='*',
        day_of_month='*',
        month_of_year='*',
    )

    PeriodicTask.objects.update_or_create(
        name=CLEANUP_TASK_NAME,
        defaults={
            'task': 'app_ui_automation.cleanup_expired_apks',
            'crontab': crontab,
            'interval': None,
            'clocked': None,
            'solar': None,
            'args': '[]',
            'kwargs': '{}',
            'queue': 'celery',
            'exchange': None,
            'routing_key': None,
            'priority': 5,
            'expires': None,
            'one_off': False,
            'start_time': None,
            'enabled': True,
            'last_run_at': None,
            'total_run_count': 0,
            'date_changed': None,
            'description': CLEANUP_TASK_DESCRIPTION,
        },
    )


def unregister_periodic_task(apps, schema_editor):
    """回滚：删除注册的定时任务"""
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name=CLEANUP_TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app_ui_automation', '0005_apppackage_apppackageversion'),
        # 用 __latest__ 让迁移能看到 django-celery-beat 后续新增的字段
        # （priority/one_off/start_time/clocked/solar 是在 0001 之后加的）
        ('django_celery_beat', '__latest__'),
    ]

    operations = [
        migrations.RunPython(register_periodic_task, unregister_periodic_task),
    ]
