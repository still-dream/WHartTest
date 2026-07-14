# -*- coding: utf-8 -*-
"""APPUI 自动化 Celery 异步任务"""

import logging
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
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
