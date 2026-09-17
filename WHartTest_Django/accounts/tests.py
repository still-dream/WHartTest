import time
from unittest.mock import patch
from types import SimpleNamespace

from django.db.utils import OperationalError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from accounts.feishu import (
    FeishuAuthError,
    build_authorize_url,
    build_state,
    exchange_code_for_token,
    get_feishu_user,
    sign_state,
    verify_state,
)
from accounts.serializers import ContentTypeSerializer
from accounts.views import MyTokenObtainPairView


class MyTokenObtainPairViewTests(SimpleTestCase):
    def setUp(self):
        # 构造 DRF 请求工厂，模拟 token 登录请求。
        self.factory = APIRequestFactory()

    def test_returns_503_when_database_not_ready(self):
        # 模拟数据库尚未就绪时的登录请求，验证接口返回 503 而不是 500 traceback。
        request = self.factory.post(
            '/api/token/',
            {'username': 'tester', 'password': 'secret'},
            format='json'
        )

        # 条件：认证流程抛出 OperationalError；动作：调用视图；结果：返回友好错误提示。
        with patch(
            'accounts.views.BaseTokenObtainPairView.post',
            side_effect=OperationalError('database is not ready')
        ):
            response = MyTokenObtainPairView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['detail'], '认证服务正在启动，请稍后重试。')


class ContentTypeSerializerMenuGroupingTests(SimpleTestCase):
    def setUp(self):
        self.serializer = ContentTypeSerializer()

    def test_api_interfaces_are_grouped_under_api_testing_menu(self):
        content_type = SimpleNamespace(app_label='api_interfaces', model='apiinterface')

        self.assertEqual(self.serializer.get_app_label_cn(content_type), '接口自动化')
        self.assertEqual(self.serializer.get_app_label_subcategory(content_type), '接口管理')
        self.assertEqual(self.serializer.get_app_label_sort(content_type), 3)

    def test_task_center_is_grouped_as_top_level_task_center_menu(self):
        content_type = SimpleNamespace(app_label='task_center', model='scheduledtask')

        self.assertEqual(self.serializer.get_app_label_cn(content_type), '任务中心')
        self.assertEqual(self.serializer.get_app_label_subcategory(content_type), '任务调度')
        self.assertEqual(self.serializer.get_app_label_sort(content_type), 5)

    def test_django_celery_beat_is_grouped_under_task_center(self):
        content_type = SimpleNamespace(app_label='django_celery_beat', model='periodictask')

        self.assertEqual(self.serializer.get_app_label_cn(content_type), '任务中心')
        self.assertEqual(self.serializer.get_app_label_subcategory(content_type), '任务调度')


@override_settings(
    FEISHU_APP_ID='cli_test',
    FEISHU_APP_SECRET='secret_test',
    FEISHU_REDIRECT_URI='http://testserver/login/feishu/callback',
)
class FeishuServiceTests(SimpleTestCase):
    def test_build_authorize_url_contains_required_params(self):
        url = build_authorize_url('my-state')

        self.assertTrue(url.startswith('https://accounts.feishu.cn/open-apis/authen/v1/authorize?'))
        self.assertIn('response_type=code', url)
        self.assertIn('client_id=cli_test', url)
        self.assertIn('state=my-state', url)
        self.assertIn(
            'redirect_uri=http%3A%2F%2Ftestserver%2Flogin%2Ffeishu%2Fcallback', url
        )

    def test_state_roundtrip_verification(self):
        self.assertTrue(verify_state(build_state()))

    def test_verify_state_rejects_tampered_signature(self):
        timestamp = str(int(time.time()))
        self.assertFalse(verify_state(f'{timestamp}.deadbeef'))

    def test_verify_state_rejects_expired_timestamp(self):
        expired_timestamp = str(int(time.time()) - 601)
        expired_state = f'{expired_timestamp}.{sign_state(expired_timestamp)}'
        self.assertFalse(verify_state(expired_state))

    def test_verify_state_rejects_malformed_state(self):
        self.assertFalse(verify_state('not-a-signed-state'))

    @patch('accounts.feishu.httpx.post')
    def test_exchange_code_for_token_returns_flat_payload(self, mock_post):
        mock_post.return_value.json.return_value = {
            'code': 0,
            'access_token': 'u-access',
            'refresh_token': 'u-refresh',
            'token_type': 'Bearer',
            'expires_in': 6900,
        }

        token_data = exchange_code_for_token('auth-code')

        self.assertEqual(token_data['access_token'], 'u-access')
        self.assertEqual(mock_post.call_args.kwargs['json']['grant_type'], 'authorization_code')
        self.assertEqual(mock_post.call_args.kwargs['json']['client_id'], 'cli_test')
        self.assertEqual(mock_post.call_args.kwargs['json']['code'], 'auth-code')
        self.assertEqual(
            mock_post.call_args.args[0], 'https://accounts.feishu.cn/oauth/v3/token'
        )

    @patch('accounts.feishu.httpx.post')
    def test_exchange_code_for_token_raises_on_error_code(self, mock_post):
        mock_post.return_value.json.return_value = {
            'code': 20004, 'error': 'invalid_code', 'error_description': 'code 已过期',
        }

        # assertLogs 捕获服务层 warning，既断言日志内容，也避免其经 lastResort 打到 stderr。
        with self.assertLogs('accounts.feishu', level='WARNING') as captured_logs:
            with self.assertRaises(FeishuAuthError):
                exchange_code_for_token('expired-code')

        self.assertIn('飞书授权码换取令牌失败', captured_logs.output[0])

    @patch('accounts.feishu.httpx.get')
    def test_get_feishu_user_returns_data_payload(self, mock_get):
        mock_get.return_value.json.return_value = {
            'code': 0,
            'data': {'name': '张三', 'email': 'zhangsan@example.com'},
        }

        feishu_user = get_feishu_user('u-access')

        self.assertEqual(feishu_user['email'], 'zhangsan@example.com')
        self.assertEqual(
            mock_get.call_args.kwargs['headers']['Authorization'], 'Bearer u-access'
        )
        self.assertEqual(
            mock_get.call_args.args[0],
            'https://open.feishu.cn/open-apis/authen/v1/user_info',
        )

    @patch('accounts.feishu.httpx.get')
    def test_get_feishu_user_raises_on_error_code(self, mock_get):
        mock_get.return_value.json.return_value = {'code': 99991668, 'msg': 'token 无效'}

        # assertLogs 捕获服务层 warning，既断言日志内容，也避免其经 lastResort 打到 stderr。
        with self.assertLogs('accounts.feishu', level='WARNING') as captured_logs:
            with self.assertRaises(FeishuAuthError):
                get_feishu_user('bad-token')

        self.assertIn('获取飞书用户信息失败', captured_logs.output[0])
