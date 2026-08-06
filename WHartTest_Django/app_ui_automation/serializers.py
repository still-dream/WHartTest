# -*- coding: utf-8 -*-
"""APPUI 自动化序列化器"""

import os

from rest_framework import serializers
from .models import (
    AppUiModule, AppUiScript, AppUiDevice,
    AppUiExecutionRecord, AppUiBatchExecutionRecord,
    AppUiExecutionConfig,
    AppPackage, AppPackageVersion,
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


# ============================================================
# APP 应用分发管理 序列化器
# ============================================================


class AppPackageVersionSerializer(serializers.ModelSerializer):
    """APP 应用版本序列化器"""
    package_name = serializers.CharField(source='package.package_name', read_only=True)
    uploader_name = serializers.CharField(source='uploader.username', read_only=True, default='')
    file_size_human = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_to_expire = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = AppPackageVersion
        fields = [
            'id', 'package', 'package_name',
            'version_name', 'version_code',
            'apk_file', 'file_size', 'file_size_human',
            'file_md5', 'file_sha1',
            'signature_sha1', 'signature_algorithm',
            'target_sdk', 'min_sdk',
            'permissions', 'main_activity', 'abi_support',
            'changelog', 'status', 'is_latest',
            'parse_status', 'parse_error',
            'is_protected', 'expire_at', 'cleaned_at',
            'days_to_expire', 'is_expired',
            'uploader', 'uploader_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'package_name', 'uploader_name', 'file_size_human',
            'is_expired', 'days_to_expire', 'is_latest',
            'expire_at', 'cleaned_at',
            'file_size', 'file_md5', 'file_sha1',
            'signature_sha1', 'signature_algorithm',
            'target_sdk', 'min_sdk', 'permissions',
            'main_activity', 'abi_support',
            'parse_status', 'parse_error',
            'uploader', 'created_at', 'updated_at',
        ]


class AppPackageSerializer(serializers.ModelSerializer):
    """APP 应用序列化器"""
    total_versions = serializers.IntegerField(read_only=True)
    latest_version = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source='creator.username', read_only=True, default='')

    class Meta:
        model = AppPackage
        fields = [
            'id', 'project', 'platform', 'package_name',
            'app_name', 'icon', 'description',
            'total_versions', 'latest_version',
            'creator', 'creator_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['creator', 'creator_name', 'total_versions', 'latest_version']

    def get_latest_version(self, obj):
        v = obj.latest_version
        if not v:
            return None
        return AppPackageVersionSerializer(v, context=self.context).data
