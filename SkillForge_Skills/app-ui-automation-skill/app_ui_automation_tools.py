# -*- coding: utf-8 -*-
"""WHartTest APP UI 自动化 Skill 工具脚本。

通过调用后端 REST API 管理 APPUI 自动化资源，包括模块、脚本、设备、
执行记录、批量执行记录和执行配置。
"""
import argparse
import io
import json
import sys
from pathlib import Path
from urllib import error, parse, request

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = 'http://127.0.0.1:8000'
API_KEY = 'wharttest-default-mcp-key-2025'
HEADERS = {
    'accept': 'application/json',
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
}
TIMEOUT = 60

# ------------------------------------------------------------------ #
# 资源定义
# ------------------------------------------------------------------ #

# 标准 CRUD 资源（list / get / create / update / delete）
CRUD_RESOURCES = [
    ('module', 'modules', 'modules', 'module_id'),
    ('device', 'devices', 'devices', 'device_id'),
]

# 部分 CRUD 资源（list / get / update / delete，无 create —— 脚本创建需通过 Web 界面上传文件）
PARTIAL_CRUD_RESOURCES = [
    ('script', 'scripts', 'scripts', 'script_id'),
]

# 只读 + 删除资源
READ_DELETE_RESOURCES = [
    ('execution_record', 'execution_records', 'execution-records', 'record_id'),
]

# 只读资源
READ_ONLY_RESOURCES = [
    ('batch_record', 'batch_records', 'batch-records', 'batch_id'),
]

ID_ARGUMENTS = [
    ('module_id', '模块 ID'),
    ('script_id', '脚本 ID'),
    ('device_id', '设备 ID'),
    ('record_id', '执行记录 ID'),
    ('batch_id', '批量执行记录 ID'),
]


# ------------------------------------------------------------------ #
# 辅助函数
# ------------------------------------------------------------------ #

def _error(message, data=None, code=None):
    result = {'status': 'error', 'message': message}
    if code is not None:
        result['code'] = code
    if data not in (None, '', {}):
        result['data'] = data
    return result


def _read_json_source(raw_value):
    if raw_value is None or raw_value == '':
        return None
    if raw_value.startswith('@'):
        return Path(raw_value[1:]).read_text(encoding='utf-8')
    return raw_value


def _load_json(raw_value, default):
    content = _read_json_source(raw_value)
    if content is None:
        return default
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f'JSON 解析失败: {exc}') from exc


def _extract_message(body, fallback):
    if isinstance(body, dict):
        for key in ('message', 'detail', 'error', 'msg'):
            value = body.get(key)
            if value:
                return value
    if isinstance(body, str) and body.strip():
        return body.strip()
    return fallback


def _build_url(url, params=None):
    if not params:
        return url
    parsed = parse.urlsplit(url)
    existing_query = parse.parse_qsl(parsed.query, keep_blank_values=True)
    extra_query = []
    for key, value in params.items():
        if isinstance(value, (list, tuple)):
            for item in value:
                extra_query.append((key, item))
        else:
            extra_query.append((key, value))
    merged_query = parse.urlencode(existing_query + extra_query, doseq=True)
    return parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, merged_query, parsed.fragment))


def _decode_response_body(raw_body):
    text = raw_body.decode('utf-8', errors='replace')
    try:
        return json.loads(text)
    except ValueError:
        return text


def _configure_request_settings(base_url, api_key):
    global API_KEY, BASE_URL
    BASE_URL = base_url.rstrip('/')
    API_KEY = api_key
    HEADERS['X-API-Key'] = API_KEY


def _request(method, url, payload=None, params=None):
    request_url = _build_url(url, params)
    request_data = None
    if payload is not None and method in {'POST', 'PUT', 'PATCH'}:
        request_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = request.Request(request_url, data=request_data, headers=HEADERS, method=method)

    try:
        with request.urlopen(req, timeout=TIMEOUT) as response:
            status_code = response.status
            body = _decode_response_body(response.read())
    except error.HTTPError as exc:
        status_code = exc.code
        body = _decode_response_body(exc.read())
    except error.URLError as exc:
        reason = getattr(exc, 'reason', exc)
        return _error(str(reason))
    except Exception as exc:
        return _error(str(exc))

    if status_code == 204:
        return {'status': 'success', 'message': '操作成功'}

    if 200 <= status_code < 300:
        if isinstance(body, dict) and 'status' in body:
            return body
        return {'status': 'success', 'data': body}

    if isinstance(body, dict) and body.get('status') == 'error':
        return body
    return _error(
        _extract_message(body, f'HTTP {status_code}'),
        data=body if isinstance(body, (dict, list)) else None,
        code=status_code,
    )


def _api_url(path):
    """构建 APP UI 自动化 API 地址（不含 project_id，项目通过 query param 过滤）"""
    return f'{BASE_URL}/api/app-ui-automation/{path.lstrip("/")}'


def _require(value, label):
    if value in (None, ''):
        raise ValueError(f'{label} 不能为空')
    return value


# ------------------------------------------------------------------ #
# 通用 CRUD 操作
# ------------------------------------------------------------------ #

def _list_resource(args, base_path):
    params = dict(args.params_obj or {})
    params.setdefault('project', args.project_id)
    return _request('GET', _api_url(f'{base_path}/'), params=params)


def _get_resource(args, base_path, id_arg):
    item_id = _require(getattr(args, id_arg), id_arg)
    return _request('GET', _api_url(f'{base_path}/{item_id}/'))


def _create_resource(args, base_path):
    payload = dict(args.payload_obj or {})
    payload.setdefault('project', args.project_id)
    return _request('POST', _api_url(f'{base_path}/'), payload=payload)


def _update_resource(args, base_path, id_arg):
    item_id = _require(getattr(args, id_arg), id_arg)
    return _request('PATCH', _api_url(f'{base_path}/{item_id}/'), payload=args.payload_obj)


def _delete_resource(args, base_path, id_arg):
    item_id = _require(getattr(args, id_arg), id_arg)
    return _request('DELETE', _api_url(f'{base_path}/{item_id}/'))


def _get_action(args, path, with_project=False):
    params = dict(args.params_obj or {})
    if with_project:
        params.setdefault('project', args.project_id)
    return _request('GET', _api_url(path), params=params)


def _post_action(args, path):
    return _request('POST', _api_url(path), payload=args.payload_obj, params=args.params_obj)


# ------------------------------------------------------------------ #
# Action 注册
# ------------------------------------------------------------------ #

def _build_actions():
    actions = {}

    # 标准 CRUD
    for singular, plural, base_path, id_arg in CRUD_RESOURCES:
        actions[f'list_{plural}'] = lambda args, p=base_path: _list_resource(args, p)
        actions[f'get_{singular}'] = lambda args, p=base_path, i=id_arg: _get_resource(args, p, i)
        actions[f'create_{singular}'] = lambda args, p=base_path: _create_resource(args, p)
        actions[f'update_{singular}'] = lambda args, p=base_path, i=id_arg: _update_resource(args, p, i)
        actions[f'delete_{singular}'] = lambda args, p=base_path, i=id_arg: _delete_resource(args, p, i)

    # 部分 CRUD（无 create）
    for singular, plural, base_path, id_arg in PARTIAL_CRUD_RESOURCES:
        actions[f'list_{plural}'] = lambda args, p=base_path: _list_resource(args, p)
        actions[f'get_{singular}'] = lambda args, p=base_path, i=id_arg: _get_resource(args, p, i)
        actions[f'update_{singular}'] = lambda args, p=base_path, i=id_arg: _update_resource(args, p, i)
        actions[f'delete_{singular}'] = lambda args, p=base_path, i=id_arg: _delete_resource(args, p, i)

    # 只读 + 删除
    for singular, plural, base_path, id_arg in READ_DELETE_RESOURCES:
        actions[f'list_{plural}'] = lambda args, p=base_path: _list_resource(args, p)
        actions[f'get_{singular}'] = lambda args, p=base_path, i=id_arg: _get_resource(args, p, i)
        actions[f'delete_{singular}'] = lambda args, p=base_path, i=id_arg: _delete_resource(args, p, i)

    # 只读
    for singular, plural, base_path, id_arg in READ_ONLY_RESOURCES:
        actions[f'list_{plural}'] = lambda args, p=base_path: _list_resource(args, p)
        actions[f'get_{singular}'] = lambda args, p=base_path, i=id_arg: _get_resource(args, p, i)

    # 自定义 actions
    actions.update({
        # 模块树
        'get_module_tree': lambda args: _get_action(args, 'modules/tree/', with_project=True),

        # 脚本预览
        'preview_script': lambda args: _get_action(
            args, f'scripts/{_require(args.script_id, "script_id")}/preview/'
        ),

        # 执行脚本（调试）
        'execute_script': lambda args: _post_action(
            args, f'scripts/{_require(args.script_id, "script_id")}/execute/'
        ),

        # 设备连接检测
        'check_device': lambda args: _post_action(
            args, f'devices/{_require(args.device_id, "device_id")}/check/'
        ),

        # 取消执行
        'cancel_execution': lambda args: _post_action(
            args, f'execution-records/{_require(args.record_id, "record_id")}/cancel/'
        ),

        # 执行配置（全局单例，pk 固定为 1）
        'get_execution_config': lambda args: _request(
            'GET', _api_url('execution-config/1/')
        ),
        'update_execution_config': lambda args: _request(
            'PATCH', _api_url('execution-config/1/'), payload=args.payload_obj
        ),
    })

    return actions


ACTIONS = _build_actions()


# ------------------------------------------------------------------ #
# 入口
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description='WHartTest APP UI 自动化 Skill 工具')
    parser.add_argument('--action', required=True, choices=sorted(ACTIONS), help='要执行的动作')
    parser.add_argument('--project_id', type=int, required=True, help='项目 ID')
    parser.add_argument('--base_url', default=BASE_URL, help='后端服务地址')
    parser.add_argument('--api_key', default=API_KEY, help='接口认证 API Key')
    parser.add_argument('--payload', help='请求体 JSON，支持 @文件路径')
    parser.add_argument('--params', help='查询参数 JSON，支持 @文件路径')

    for arg_name, help_text in ID_ARGUMENTS:
        parser.add_argument(f'--{arg_name}', type=int, help=help_text)

    args = parser.parse_args()

    try:
        _configure_request_settings(args.base_url, args.api_key)
        args.payload_obj = _load_json(args.payload, {})
        args.params_obj = _load_json(args.params, {})
        result = ACTIONS[args.action](args)
    except ValueError as exc:
        result = _error(str(exc))
    except FileNotFoundError as exc:
        result = _error(f'文件不存在: {exc.filename}')
    except Exception as exc:
        result = _error(str(exc))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if isinstance(result, dict) and result.get('status') == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
