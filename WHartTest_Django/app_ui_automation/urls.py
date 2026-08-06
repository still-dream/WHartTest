# -*- coding: utf-8 -*-
"""APPUI 自动化路由配置"""

from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    AppUiModuleViewSet, AppUiScriptViewSet, AppUiDeviceViewSet,
    AppUiExecutionRecordViewSet, AppUiBatchExecutionRecordViewSet,
    AppUiExecutionConfigViewSet, public_report_view,
    AppPackageViewSet, AppPackageVersionViewSet, AppCleanupViewSet,
)

router = DefaultRouter()
router.register('modules', AppUiModuleViewSet, basename='app-ui-modules')
router.register('scripts', AppUiScriptViewSet, basename='app-ui-scripts')
router.register('devices', AppUiDeviceViewSet, basename='app-ui-devices')
router.register('execution-records', AppUiExecutionRecordViewSet, basename='app-ui-execution-records')
router.register('batch-records', AppUiBatchExecutionRecordViewSet, basename='app-ui-batch-records')
router.register('execution-config', AppUiExecutionConfigViewSet, basename='app-ui-execution-config')
router.register('app-packages', AppPackageViewSet, basename='app-ui-app-packages')
router.register('app-package-versions', AppPackageVersionViewSet, basename='app-ui-app-package-versions')
router.register('app-cleanup', AppCleanupViewSet, basename='app-ui-app-cleanup')

urlpatterns = router.urls + [
    path('public-report/', public_report_view, name='public-report'),
]
