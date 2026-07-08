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
    """串行执行多个脚本（定时任务）

    Args:
        batch_record_id: 批量执行记录 ID
        script_ids: 要执行的脚本 ID 列表
        device_id: 执行设备 ID（可选）
    """
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
            # 同步执行（串行：前一个完成后再执行下一个）
            executor.execute(record.id)
        except Exception as e:
            logger.error(f"脚本执行失败, script_id={script_id}: {e}")
            AppUiExecutionRecord.objects.create(
                batch=batch, script_id=script_id, device_id=device_id,
                trigger_type='scheduled', status=3, error_message=str(e),
                start_time=timezone.now(), end_time=timezone.now(),
            )

    # 更新批次统计
    batch.update_statistics()
    logger.info(f"批量执行完成, batch_id={batch_record_id}")
