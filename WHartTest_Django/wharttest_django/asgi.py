"""
ASGI config for wharttest_django project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

# 设置 umask 确保新建文件有正确的权限（664 文件，775 目录）
os.umask(0o002)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wharttest_django.settings')

import django
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

# 导入 WebSocket 路由
from testcases.routing import websocket_urlpatterns

# Django ASGI 应用
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    # HTTP 请求使用 Django ASGI 处理
    "http": django_asgi_app,
    # WebSocket 请求使用 Channels 处理
    "websocket": AllowedHostsOriginValidator(
        URLRouter(websocket_urlpatterns)
    ),
})
