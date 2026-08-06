# -*- coding: utf-8 -*-
"""APPUI 自动化 Celery 异步任务"""

import logging
import os
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

from .models import AppUiExecutionRecord, AppUiBatchExecutionRecord, AppUiScript, AppPackageVersion
from .executor import AppUiScriptExecutor

logger = logging.getLogger(__name__)


@shared_task
def execute_app_ui_script(execution_record_id):
    """执行单个 APPUI 脚本"""
    logger.info(f"开始执行 APPUI 脚本, record_id={execution_record_id}")
    executor = AppUiScriptExecutor()
    executor.execute(execution_record_id)


@shared_task(
    soft_time_limit=4 * 3600,
    time_limit=4 * 3600 + 300,
)
def execute_app_ui_batch(batch_record_id, script_ids, device_id=None,
                         scheduled_task_id=None, execution_id=None):
    """串行执行多个脚本（定时任务）

    Args:
        batch_record_id: 批量执行记录 ID
        script_ids: 要执行的脚本 ID 列表
        device_id: 执行设备 ID（可选）
        scheduled_task_id: 定时任务 ID（可选，用于完成后发送通知）
        execution_id: 执行记录 ID（可选，用于完成后发送通知）
    """
    logger.info(f"批量执行, batch_id={batch_record_id}, scripts={script_ids}")
    batch = AppUiBatchExecutionRecord.objects.get(id=batch_record_id)
    batch.status = 1
    batch.start_time = timezone.now()
    batch.save()

    executor = AppUiScriptExecutor()

    try:
        for script_id in script_ids:
            try:
                record = AppUiExecutionRecord.objects.create(
                    batch=batch, script_id=script_id, device_id=device_id,
                    trigger_type='scheduled', status=0,
                )
                # 同步执行（串行：前一个完成后再执行下一个）
                executor.execute(record.id)
            except Exception as e:
                logger.error(f"脚本执行失败, script_id={script_id}: {e}")
                AppUiExecutionRecord.objects.create(
                    batch=batch, script_id=script_id, device_id=device_id,
                    trigger_type='scheduled', status=3, error_message=str(e),
                    start_time=timezone.now(), end_time=timezone.now(),
                )
    except SoftTimeLimitExceeded:
        logger.warning(f"批量执行超时, batch_id={batch_record_id}")
    except Exception as e:
        logger.error(f"批量执行异常, batch_id={batch_record_id}: {e}")
    finally:
        # 更新批次统计
        try:
            batch.refresh_from_db()
            batch.update_statistics()
        except Exception as e:
            logger.error(f"更新批次统计失败, batch_id={batch_record_id}: {e}")

        logger.info(f"批量执行完成, batch_id={batch_record_id}")

        # 定时任务触发时，更新执行记录并发送 webhook 通知
        if scheduled_task_id and execution_id:
            _finalize_scheduled_execution(scheduled_task_id, execution_id, batch)


def _finalize_scheduled_execution(scheduled_task_id, execution_id, batch):
    """定时任务执行完成后，更新执行记录状态并发送 webhook 通知"""
    from task_center.models import ScheduledTask, TaskExecution
    from notifications.services import send_task_notification

    try:
        task = ScheduledTask.objects.get(id=scheduled_task_id)
        execution = TaskExecution.objects.get(id=execution_id)

        batch.refresh_from_db()
        if batch.status == 2:
            execution.status = TaskExecution.ExecutionStatus.SUCCESS
        else:
            execution.status = TaskExecution.ExecutionStatus.FAILED
        execution.finished_at = timezone.now()
        execution.log += f'\nAPPUI batch {batch.id} completed\n'
        execution.save()

        try:
            send_task_notification(task, execution, batch)
        except Exception as push_err:
            logger.warning(f"推送通知失败: {push_err}")

        # 一次性任务执行后自动禁用
        if task.schedule_type == ScheduledTask.ScheduleType.ONCE:
            task.status = ScheduledTask.TaskStatus.DISABLED
            task.save(update_fields=['status'])
    except Exception as e:
        logger.error(f"更新定时任务执行记录失败: {e}")


# ============================================================
# APP 应用分发管理 - 定时清理过期 APK
# ============================================================

@shared_task(name='app_ui_automation.cleanup_expired_apks')
def cleanup_expired_apks(dry_run=False, retention_days=None):
    """清理过期的 APP 安装包（默认 30 天前上传的）

    清理规则：
      - 达到 expire_at 时间（默认上传后 30 天）
      - 未被标记为受保护（is_protected=False）
      - 数据库记录保留，仅删除磁盘文件 + 标记 cleaned_at

    Args:
        dry_run: True 时仅扫描不删除，用于预演
        retention_days: 覆盖默认保留天数（None 表示用模型默认值）

    Returns:
        dict: {scanned, deleted, skipped, freed_bytes, errors}
    """
    from datetime import timedelta
    from django.conf import settings as dj_settings

    now = timezone.now()
    effective_retention = retention_days if retention_days is not None else AppPackageVersion.RETENTION_DAYS

    # 1. 扫描候选
    qs = AppPackageVersion.objects.filter(
        is_protected=False,
        cleaned_at__isnull=True,
    ).filter(expire_at__lte=now).select_related('package')

    scanned = qs.count()
    deleted = 0
    skipped = 0
    freed_bytes = 0
    errors = []

    for version in qs:
        try:
            file_path = version.apk_file.path if version.apk_file else None
            file_size = version.file_size or 0

            if dry_run:
                logger.info(
                    f"[DRY-RUN] 将清理 {version.package.package_name} "
                    f"v{version.version_name} ({version.file_size_human}), "
                    f"过期时间 {version.expire_at.isoformat()}"
                )
                skipped += 1
                continue

            # 2. 删除磁盘文件
            if file_path and os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    freed_bytes += file_size
                except OSError as e:
                    logger.warning(f"删除 APK 文件失败 {file_path}: {e}")
                    errors.append(f"{version.id}: {e}")
                    continue

            # 3. 清空 FileField 字段，标记清理时间
            #    保留数据库记录，仅移除文件引用，便于审计
            version.apk_file = None
            version.file_size = 0
            version.cleaned_at = now
            version.save(update_fields=['apk_file', 'file_size', 'cleaned_at', 'updated_at'])

            deleted += 1
            logger.info(
                f"已清理 APK: {version.package.package_name} v{version.version_name}, "
                f"释放 {version.file_size_human}"
            )
        except Exception as e:
            logger.exception(f"清理 APK 版本 {version.id} 失败: {e}")
            errors.append(f"{version.id}: {e}")

    summary = {
        'scanned': scanned,
        'deleted': deleted,
        'skipped': skipped,
        'freed_bytes': freed_bytes,
        'freed_human': _humanize_size(freed_bytes),
        'retention_days': effective_retention,
        'dry_run': dry_run,
        'errors': errors[:20],  # 最多保留 20 条错误
    }
    logger.info(f"APK 自动清理任务完成: {summary}")
    return summary


def _humanize_size(size):
    """人类可读的文件大小"""
    size = float(size)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"
