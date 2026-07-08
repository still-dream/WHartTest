# -*- coding: utf-8 -*-
"""APPUI 自动化路由配置"""

from rest_framework.routers import DefaultRouter
from .views import (
    AppUiModuleViewSet, AppUiScriptViewSet, AppUiDeviceViewSet,
    AppUiExecutionRecordViewSet, AppUiBatchExecutionRecordViewSet
)

router = DefaultRouter()
router.register('modules', AppUiModuleViewSet, basename='app-ui-modules')
router.register('scripts', AppUiScriptViewSet, basename='app-ui-scripts')
router.register('devices', AppUiDeviceViewSet, basename='app-ui-devices')
router.register('execution-records', AppUiExecutionRecordViewSet, basename='app-ui-execution-records')
router.register('batch-records', AppUiBatchExecutionRecordViewSet, basename='app-ui-batch-records')

urlpatterns = router.urls
