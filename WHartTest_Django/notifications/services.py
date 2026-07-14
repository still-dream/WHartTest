"""推送服务模块 - Task 4 中完善"""


def build_feishu_card(rendered_content, status, report_url, task_url):
    """构建飞书交互卡片 JSON（占位实现，Task 4 完善）"""
    return {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': '测试任务执行通知'},
                'template': 'green' if status == 'success' else 'red',
            },
            'elements': [
                {
                    'tag': 'markdown',
                    'content': rendered_content,
                },
            ],
        },
    }
