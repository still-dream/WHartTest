from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app_ui_automation', '0003_appuibatchexecutionrecord_appuidevice_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppUiExecutionConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('airtest_threshold', models.FloatField(default=0.6, help_text='0-1 之间，值越低匹配越宽松', verbose_name='图像匹配阈值')),
                ('airtest_find_timeout', models.IntegerField(default=30, verbose_name='元素查找超时（秒）')),
                ('airtest_opdelay', models.FloatField(default=1.0, verbose_name='操作间隔延迟（秒）')),
                ('poco_wait_timeout', models.IntegerField(default=20, help_text='修改后需重新连接设备才生效', verbose_name='Poco元素等待超时（秒）')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='app_ui_config_updates', to='auth.user', verbose_name='更新人')),
            ],
            options={
                'verbose_name': 'APPUI 执行配置',
                'verbose_name_plural': 'APPUI 执行配置',
                'db_table': 'app_ui_execution_config',
            },
        ),
    ]
