from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OperationLog',
            fields=[
                ('id', models.BigAutoField(serialize=False, auto_created=True, primary_key=True)),
                ('username', models.CharField(db_index=True, max_length=150, verbose_name='用户名')),
                ('feature', models.CharField(db_index=True, help_text='用户访问的功能模块或页面', max_length=200, verbose_name='功能点')),
                ('path', models.CharField(blank=True, max_length=500, null=True, verbose_name='访问路径')),
                ('method', models.CharField(blank=True, max_length=10, null=True, verbose_name='请求方法')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP地址')),
                ('user_agent', models.TextField(blank=True, null=True, verbose_name='用户代理')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='访问时间')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='operation_logs', to='accounts.user', verbose_name='用户')),
            ],
            options={
                'verbose_name': '操作日志',
                'verbose_name_plural': '操作日志',
                'db_table': 'operation_logs',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user'], name='accounts_o_user_id_idx'),
                    models.Index(fields=['created_at'], name='accounts_o_created_at_idx'),
                    models.Index(fields=['-created_at'], name='accounts_o_created_at_desc_idx'),
                    models.Index(fields=['user', '-created_at'], name='accounts_o_user_created_idx'),
                ],
            },
        ),
    ]
