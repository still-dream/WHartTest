from rest_framework import serializers
from .models import ScheduledTask, TaskExecution
from ui_automation.models import UiTestCase
from app_ui_automation.models import AppUiScript, AppUiDevice
from notifications.models import WebhookAddress


class ScheduledTaskSerializer(serializers.ModelSerializer):
    schedule_display = serializers.SerializerMethodField()
    creator_name = serializers.SerializerMethodField()
    test_suite_name = serializers.SerializerMethodField()
    environment_name = serializers.SerializerMethodField()
    ui_environment_name = serializers.SerializerMethodField()
    ui_testcase_ids = serializers.PrimaryKeyRelatedField(
        source='ui_testcases', many=True,
        queryset=UiTestCase.objects.all(), required=False
    )
    app_ui_scripts = serializers.PrimaryKeyRelatedField(
        many=True, queryset=AppUiScript.objects.all(), required=False
    )
    app_ui_device = serializers.PrimaryKeyRelatedField(
        queryset=AppUiDevice.objects.all(), required=False, allow_null=True
    )
    webhook_addresses = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=WebhookAddress.objects.filter(is_active=True),
        required=False
    )

    class Meta:
        model = ScheduledTask
        fields = [
            'id', 'name', 'description', 'project', 'module',
            'execution_target', 'schedule_type', 'once_datetime',
            'daily_time', 'weekly_days', 'weekly_time', 'hourly_minute',
            'retry_enabled', 'retry_count', 'retry_interval',
            'status', 'last_run_at', 'creator', 'creator_name',
            'schedule_display', 'created_at', 'updated_at',
            'test_suite', 'test_suite_name', 'ui_testcase_ids',
            'actuator_id',
            'environment', 'environment_name',
            'ui_environment', 'ui_environment_name',
            'app_ui_scripts', 'app_ui_device',
            'push_config', 'webhook_addresses', 'push_message_content',
        ]
        read_only_fields = [
            'project', 'status', 'last_run_at', 'creator', 'creator_name',
            'schedule_display', 'created_at', 'updated_at',
            'test_suite_name', 'environment_name', 'ui_environment_name',
        ]
        extra_kwargs = {
            'environment': {'required': False, 'allow_null': True},
            'ui_environment': {'required': False, 'allow_null': True},
        }

    def get_schedule_display(self, obj):
        return obj.get_schedule_display_text()

    def get_creator_name(self, obj):
        if obj.creator:
            return obj.creator.get_full_name() or obj.creator.username
        return None

    def get_test_suite_name(self, obj):
        if obj.test_suite:
            return obj.test_suite.name
        return None

    def get_environment_name(self, obj):
        if obj.environment_id:
            return obj.environment.name
        return None

    def get_ui_environment_name(self, obj):
        if obj.ui_environment_id:
            return obj.ui_environment.name
        return None

    def validate_environment(self, value):
        """校验环境属于当前项目（仅在填写时校验）"""
        # 处理空值：None、0、空字符串都视为未选择
        if value is None or (hasattr(value, 'id') and value.id in (None, 0)):
            return None
        project = self.context.get('project')
        if project is not None and value.project_id != project.id:
            raise serializers.ValidationError('所选环境不属于当前项目')
        return value

    def validate_ui_environment(self, value):
        """校验 UI 环境配置属于当前项目（仅在填写时校验）"""
        if value is None:
            return value
        project = self.context.get('project')
        if project is not None and value.project_id != project.id:
            raise serializers.ValidationError('所选 UI 环境配置不属于当前项目')
        return value

    def validate_name(self, value):
        if len(value) > 50:
            raise serializers.ValidationError('任务名称最大长度为50字符')
        return value

    def validate(self, attrs):
        schedule_type = attrs.get('schedule_type', getattr(self.instance, 'schedule_type', None))
        module = attrs.get('module', getattr(self.instance, 'module', None))

        # 模块关联验证
        if module == ScheduledTask.TaskModule.TEST_SUITE:
            if not attrs.get('test_suite') and not getattr(self.instance, 'test_suite', None):
                raise serializers.ValidationError({'test_suite': '测试套件模块必须关联一个测试套件'})

        # UI 自动化模块 → ui_environment 必填，environment 非必填
        if module == ScheduledTask.TaskModule.UI_AUTOMATION:
            ui_env = attrs.get('ui_environment', getattr(self.instance, 'ui_environment_id', None))
            if not ui_env:
                raise serializers.ValidationError({'ui_environment': 'UI 自动化模块必须选择 UI 环境配置'})

        # 测试套件模块 → environment 必填
        if module == ScheduledTask.TaskModule.TEST_SUITE:
            env = attrs.get('environment', getattr(self.instance, 'environment_id', None))
            if not env:
                raise serializers.ValidationError({'environment': '测试套件模块必须选择 API 环境配置'})

        if schedule_type == ScheduledTask.ScheduleType.ONCE:
            if not attrs.get('once_datetime') and not getattr(self.instance, 'once_datetime', None):
                raise serializers.ValidationError({'once_datetime': '仅执行一次时必须指定执行时间'})
        elif schedule_type == ScheduledTask.ScheduleType.DAILY:
            if not attrs.get('daily_time') and not getattr(self.instance, 'daily_time', None):
                raise serializers.ValidationError({'daily_time': '每天执行时必须指定时间'})
        elif schedule_type == ScheduledTask.ScheduleType.WEEKLY:
            weekly_days = attrs.get('weekly_days', getattr(self.instance, 'weekly_days', None))
            if not weekly_days:
                raise serializers.ValidationError({'weekly_days': '每周执行时必须选择至少一天'})
            if not attrs.get('weekly_time') and not getattr(self.instance, 'weekly_time', None):
                raise serializers.ValidationError({'weekly_time': '每周执行时必须指定时间'})
        elif schedule_type == ScheduledTask.ScheduleType.HOURLY:
            hourly_minute = attrs.get('hourly_minute', getattr(self.instance, 'hourly_minute', None))
            if hourly_minute is None:
                raise serializers.ValidationError({'hourly_minute': '每小时执行时必须指定分钟数'})

        # APPUI 自动化模块校验
        if module == ScheduledTask.TaskModule.APP_UI_AUTOMATION:
            app_ui_scripts = attrs.get('app_ui_scripts', None)
            if app_ui_scripts is not None:
                if hasattr(app_ui_scripts, 'all'):
                    script_count = app_ui_scripts.count()
                elif isinstance(app_ui_scripts, list):
                    script_count = len(app_ui_scripts)
                else:
                    script_count = 0
            elif self.instance:
                script_count = self.instance.app_ui_scripts.count()
            else:
                script_count = 0
            if not script_count:
                raise serializers.ValidationError({'app_ui_scripts': 'APPUI 自动化模块必须选择至少一个脚本'})

            app_ui_device = attrs.get('app_ui_device', getattr(self.instance, 'app_ui_device_id', None) if self.instance else None)
            if not app_ui_device:
                raise serializers.ValidationError({'app_ui_device': 'APPUI 自动化模块必须选择执行设备'})

        # 推送配置校验
        push_config = attrs.get('push_config', getattr(self.instance, 'push_config', 'always') if self.instance else 'always')
        if push_config != 'disabled':
            push_content = attrs.get('push_message_content', getattr(self.instance, 'push_message_content', '') if self.instance else '')
            if not push_content:
                raise serializers.ValidationError({'push_message_content': '启用推送时必须填写消息内容'})
            webhooks = attrs.get('webhook_addresses', None)
            if webhooks is not None:
                webhook_count = len(webhooks) if isinstance(webhooks, list) else 0
            elif self.instance:
                webhook_count = self.instance.webhook_addresses.count()
            else:
                webhook_count = 0
            if webhook_count == 0:
                raise serializers.ValidationError({'webhook_addresses': '启用推送时至少选择一个推送地址'})

        return attrs


class TaskExecutionSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()

    class Meta:
        model = TaskExecution
        fields = [
            'id', 'execution_id', 'task', 'trigger_type', 'status',
            'started_at', 'finished_at', 'duration', 'log', 'error_message',
        ]
        read_only_fields = fields

    def get_duration(self, obj):
        return obj.duration_display
