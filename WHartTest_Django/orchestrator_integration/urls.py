"""URL路由配置"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrchestratorTaskViewSet, OrchestratorStreamAPIView
from .agent_loop_view import AgentLoopStreamAPIView

router = DefaultRouter()
router.register(r'tasks', OrchestratorTaskViewSet, basename='orchestrator-task')

urlpatterns = [
    path('', include(router.urls)),
    # 流式对话接口 - Brain调用Agent的主要接口
    path('stream/', OrchestratorStreamAPIView.as_view(), name='orchestrator-stream'),
    # Agent Loop 流式对话接口 - 解决 Token 累积问题
    path('agent-loop/', AgentLoopStreamAPIView.as_view(), name='agent-loop-stream'),
]
