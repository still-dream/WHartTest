"""推送服务：变量渲染 + 飞书卡片构建 + HTTP 发送"""
import logging
import os
from pathlib import Path

import requests as http_requests
from django.conf import settings

from .variables import build_context, render_content

logger = logging.getLogger(__name__)


# ============================== 飞书图片上传 ==============================

def _get_feishu_token():
    """获取飞书 tenant_access_token"""
    app_id = getattr(settings, 'FEISHU_APP_ID', '')
    app_secret = getattr(settings, 'FEISHU_APP_SECRET', '')
    if not app_id or not app_secret:
        return None

    try:
        resp = http_requests.post(
            'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            json={'app_id': app_id, 'app_secret': app_secret},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get('tenant_access_token')
    except Exception as e:
        logger.warning(f"获取飞书 token 失败: {e}")
    return None


def _upload_feishu_image(token, image_path):
    """上传图片到飞书，返回 image_key"""
    if not os.path.isfile(image_path):
        return None

    try:
        with open(image_path, 'rb') as f:
            resp = http_requests.post(
                'https://open.feishu.cn/open-apis/im/v1/images',
                headers={'Authorization': f'Bearer {token}'},
                data={'image_type': 'message'},
                files={'image': f},
                timeout=15,
            )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('image_key')
    except Exception as e:
        logger.warning(f"上传飞书图片失败: {e}")
    return None


def _get_report_screenshot(task, module_result):
    """获取 APPUI 报告截图的飞书 image_key"""
    from task_center.models import ScheduledTask

    if task.module != ScheduledTask.TaskModule.APP_UI_AUTOMATION or not module_result:
        return None

    # 查找最后一条有报告的执行记录
    last_record = module_result.execution_records.exclude(
        report_path=''
    ).order_by('-id').first()
    if not last_record or not last_record.report_path:
        return None

    # 推导截图路径（executor 中生成的是 .jpg）
    report_path = Path(settings.MEDIA_ROOT) / last_record.report_path
    screenshot_path = report_path.with_suffix('.jpg')

    if not os.path.isfile(screenshot_path):
        logger.warning(f"报告截图不存在: {screenshot_path}")
        return None

    token = _get_feishu_token()
    if not token:
        logger.warning("飞书 APP_ID/APP_SECRET 未配置或获取 token 失败，跳过图片上传")
        return None

    image_key = _upload_feishu_image(token, str(screenshot_path))
    if not image_key:
        logger.warning("上传飞书图片失败，仅发送文本通知")
    return image_key


# ============================== 飞书卡片构建 ==============================


def build_feishu_card(rendered_content, status, image_key=None):
    """构建飞书交互卡片 JSON（JSON 2.0）"""
    header_template = 'green' if status == 'success' else 'red'

    elements = [
        {
            'tag': 'markdown',
            'content': rendered_content,
        },
    ]

    if image_key:
        elements.append({
            'tag': 'img',
            'img_key': image_key,
            'alt': {'tag': 'plain_text', 'content': '测试报告截图'},
        })

    return {
        'msg_type': 'interactive',
        'card': {
            'schema': '2.0',
            'header': {
                'title': {
                    'tag': 'plain_text',
                    'content': '测试任务执行通知',
                },
                'template': header_template,
            },
            'body': {
                'elements': elements,
            },
        },
    }


# ============================== 推送入口 ==============================

def send_task_notification(task, execution, module_result):
    """任务执行完成后调用，发送推送通知"""
    logger.info(
        f"开始发送通知: task={task.name}, push_config={task.push_config}, "
        f"execution.status={execution.status}, module={task.module}"
    )

    if task.push_config == 'disabled':
        logger.info(f"跳过推送: 任务 [{task.name}] push_config=disabled")
        return
    if task.push_config == 'failure_only' and execution.status == 'success':
        logger.info(f"跳过推送: 任务 [{task.name}] push_config=failure_only 且执行成功")
        return

    # APPUI 任务需要 batch 对象来填充统计数据，若为 None 则记录日志并跳过
    from task_center.models import ScheduledTask
    if task.module == ScheduledTask.TaskModule.APP_UI_AUTOMATION and not module_result:
        logger.warning(
            f"APPUI 任务 [{task.name}] 的 batch 对象为 None，"
            f"无法获取统计数据，跳过发送通知"
        )
        return

    context = build_context(task, execution, module_result)
    rendered = render_content(task.push_message_content or '', context)

    # 尝试获取报告截图并上传到飞书
    image_key = _get_report_screenshot(task, module_result)

    card = build_feishu_card(
        rendered,
        'success' if context['status'] == '成功' else 'failed',
        image_key=image_key,
    )

    active_webhooks = task.webhook_addresses.filter(is_active=True)
    webhook_count = active_webhooks.count()
    if webhook_count == 0:
        logger.warning(
            f"跳过推送: 任务 [{task.name}] 没有关联活跃的 webhook 地址"
        )
        return

    logger.info(f"任务 [{task.name}] 准备推送到 {webhook_count} 个 webhook 地址")
    for addr in active_webhooks:
        try:
            resp = http_requests.post(addr.url, json=card, timeout=10)
            if resp.status_code != 200:
                logger.warning(
                    f"推送失败 {addr.name}: HTTP {resp.status_code}, "
                    f"response={resp.text[:200]}"
                )
            else:
                resp_data = resp.json()
                if resp_data.get('code') != 0 and resp_data.get('StatusCode') != 0:
                    logger.warning(
                        f"推送失败 {addr.name}: 飞书返回错误, "
                        f"response={resp.text[:200]}"
                    )
                else:
                    logger.info(f"推送成功 {addr.name}")
        except Exception as e:
            logger.warning(f"推送失败 {addr.name}: {e}")
