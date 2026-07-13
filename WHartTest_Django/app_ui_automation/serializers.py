# -*- coding: utf-8 -*-
"""APPUI 自动化序列化器"""

import os

from rest_framework import serializers
from .models import (
    AppUiModule, AppUiScript, AppUiDevice,
    AppUiExecutionRecord, AppUiBatchExecutionRecord,
    AppUiExecutionConfig
)


class AppUiModuleSerializer(serializers.ModelSerializer):
    """模块序列化器"""
    children = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = AppUiModule
        fields = ['id', 'project', 'name', 'parent', 'level', 'children',
                  'creator', 'creator_name', 'created_at', 'updated_at']
        read_only_fields = ['level', 'creator', 'created_at', 'updated_at']

    def get_children(self, obj):
        children = obj.children.all()
        return AppUiModuleSerializer(children, many=True).data if children else []


class AppUiScriptSerializer(serializers.ModelSerializer):
    """脚本序列化器"""
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = AppUiScript
        fields = ['id', 'project', 'module', 'module_name', 'name', 'description',
                  'platform', 'script_file', 'script_dir', 'script_entry',
                  'level', 'status', 'creator', 'creator_name',
                  'created_at', 'updated_at']
        read_only_fields = ['script_dir', 'script_entry', 'status',
                            'creator', 'created_at', 'updated_at']

    def validate_script_file(self, value):
        """验证脚本文件格式，支持 .zip/.air/.py"""
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in ('.zip', '.air', '.py'):
            raise serializers.ValidationError('不支持的文件格式，请上传 .zip、.air 或 .py 文件')
        return value


class AppUiDeviceSerializer(serializers.ModelSerializer):
    """设备序列化器"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = AppUiDevice
        fields = '__all__'
        read_only_fields = ['creator', 'created_at', 'updated_at']


class AppUiExecutionRecordSerializer(serializers.ModelSerializer):
    """执行记录序列化器"""
    script_name = serializers.CharField(source='script.name', read_only=True)
    device_name = serializers.CharField(source='device.name', read_only=True, default='')
    executor_name = serializers.CharField(source='executor.username', read_only=True, default='')

    class Meta:
        model = AppUiExecutionRecord
        fields = '__all__'


class AppUiBatchExecutionRecordSerializer(serializers.ModelSerializer):
    """批量执行记录序列化器"""
    executor_name = serializers.CharField(source='executor.username', read_only=True, default='')

    class Meta:
        model = AppUiBatchExecutionRecord
        fields = '__all__'


class AppUiExecutionConfigSerializer(serializers.ModelSerializer):
    """执行配置序列化器"""
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True, default='')

    class Meta:
        model = AppUiExecutionConfig
        fields = ['id', 'airtest_threshold', 'airtest_find_timeout',
                  'airtest_opdelay', 'poco_wait_timeout',
                  'updated_by', 'updated_by_name', 'updated_at']
        read_only_fields = ['id', 'updated_by', 'updated_at']
