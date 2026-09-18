# -*- coding: utf-8 -*-
"""新增 APP 应用 + APP 应用版本 数据模型（APK 分发管理核心表）"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_ui_automation', '0004_appui_execution_config'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AppPackage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(default='android', max_length=10, verbose_name='平台')),
                ('package_name', models.CharField(db_index=True, help_text='例如：com.example.app', max_length=200, verbose_name='包名')),
                ('app_name', models.CharField(blank=True, default='', max_length=200, verbose_name='应用名称')),
                ('icon', models.ImageField(blank=True, null=True, upload_to='app_icons/', verbose_name='图标')),
                ('description', models.TextField(blank=True, default='', verbose_name='应用描述')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('creator', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_app_packages', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='app_packages', to='projects.project', verbose_name='所属项目')),
            ],
            options={
                'verbose_name': 'APP 应用',
                'verbose_name_plural': 'APP 应用',
                'db_table': 'app_package',
                'ordering': ['-updated_at'],
                'unique_together': {('project', 'package_name')},
            },
        ),
        migrations.CreateModel(
            name='AppPackageVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_name', models.CharField(help_text='如：1.2.3', max_length=50, verbose_name='版本号')),
                ('version_code', models.IntegerField(help_text='如：123', verbose_name='版本代码')),
                ('apk_file', models.FileField(upload_to='app_packages/', verbose_name='APK 文件')),
                ('file_size', models.BigIntegerField(default=0, verbose_name='文件大小(字节)')),
                ('file_md5', models.CharField(blank=True, default='', max_length=32, verbose_name='MD5')),
                ('file_sha1', models.CharField(blank=True, default='', max_length=40, verbose_name='SHA1')),
                ('signature_sha1', models.CharField(blank=True, default='', max_length=100, verbose_name='签名 SHA1')),
                ('signature_algorithm', models.CharField(blank=True, default='', max_length=50, verbose_name='签名算法')),
                ('target_sdk', models.IntegerField(blank=True, null=True, verbose_name='目标 SDK')),
                ('min_sdk', models.IntegerField(blank=True, null=True, verbose_name='最低 SDK')),
                ('permissions', models.JSONField(default=list, verbose_name='权限列表')),
                ('main_activity', models.CharField(blank=True, default='', max_length=300, verbose_name='启动 Activity')),
                ('abi_support', models.JSONField(default=list, verbose_name='支持 ABI')),
                ('changelog', models.TextField(blank=True, default='', verbose_name='版本说明')),
                ('status', models.CharField(choices=[('draft', '草稿'), ('released', '已发布'), ('deprecated', '已废弃'), ('prerelease', '预发布')], default='released', max_length=20, verbose_name='状态')),
                ('is_latest', models.BooleanField(default=False, verbose_name='是否最新版本')),
                ('parse_status', models.CharField(choices=[('pending', '待解析'), ('parsing', '解析中'), ('success', '解析成功'), ('failed', '解析失败')], default='pending', max_length=20, verbose_name='解析状态')),
                ('parse_error', models.TextField(blank=True, default='', verbose_name='解析错误')),
                ('is_protected', models.BooleanField(default=False, help_text='勾选后即使超过保留期也不会被自动清理', verbose_name='受保护（不自动清理）')),
                ('expire_at', models.DateTimeField(blank=True, help_text='达到该时间后将被自动清理，默认上传后 30 天', null=True, verbose_name='过期时间')),
                ('cleaned_at', models.DateTimeField(blank=True, help_text='被自动清理的时间', null=True, verbose_name='清理时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='上传时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('uploader', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_app_versions', to=settings.AUTH_USER_MODEL, verbose_name='上传人')),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='app_ui_automation.apppackage', verbose_name='所属应用')),
            ],
            options={
                'verbose_name': 'APP 应用版本',
                'verbose_name_plural': 'APP 应用版本',
                'db_table': 'app_package_version',
                'ordering': ['-version_code', '-created_at'],
                'unique_together': {('package', 'version_code')},
                'indexes': [
                    models.Index(fields=['expire_at', 'is_protected'], name='app_package__expire__b8a4e1_idx'),
                    models.Index(fields=['status'], name='app_package__status__5b9c2d_idx'),
                ],
            },
        ),
    ]
