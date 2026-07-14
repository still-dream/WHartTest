"""推送服务：变量渲染 + 飞书卡片构建 + HTTP 发送"""
import logging
import requests as http_requests

from .variables import build_context, render_content

logger = logging.getLogger(__name__)


def build_feishu_card(rendered_content, status, report_url, task_url):
    """构建飞书交互卡片 JSON"""
    header_template = 'green' if status == 'success' else 'red'

    elements = [
        {
            'tag': 'markdown',
            'content': rendered_content,
        },
    ]

    actions = []
    if report_url:
        actions.append({
            'tag': 'button',
            'text': {'tag': 'plain_text', 'content': '查看完整报告'},
            'type': 'link',
            'url': report_url,
        })
    if task_url:
        actions.append({
            'tag': 'button',
            'text': {'tag': 'plain_text', 'content': '任务详情'},
            'type': 'link',
            'url': task_url,
        })
    if actions:
        elements.append({
            'tag': 'action',
            'actions': actions,
        })

    return {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {
                    'tag': 'plain_text',
                    'content': '测试任务执行通知',
                },
                'template': header_template,
            },
            'elements': elements,
        },
    }


def send_task_notification(task, execution, module_result):
    """任务执行完成后调用，发送推送通知"""
    if task.push_config == 'disabled':
        return
    if task.push_config == 'failure_only' and execution.status == 'success':
        return

    context = build_context(task, execution, module_result)
    rendered = render_content(task.push_message_content or '', context)

    for addr in task.webhook_addresses.filter(is_active=True):
        card = build_feishu_card(
            rendered,
            'success' if context['status'] == '成功' else 'failed',
            context.get('report_url', ''),
            context.get('task_url', ''),
        )
        try:
            resp = http_requests.post(addr.url, json=card, timeout=10)
            if resp.status_code != 200:
                logger.warning(
                    f"推送失败 {addr.name}: HTTP {resp.status_code}, "
                    f"response={resp.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"推送失败 {addr.name}: {e}")
