---
name: app-ui-automation
description: WHartTest APP UI 自动化管理工具。基于 Airtest/Poco 的移动端 APP 自动化测试，用于管理 APPUI 模块、Airtest 脚本、测试设备、执行配置、执行记录和批量执行。支持脚本调试执行、设备连接检测、执行记录查看与报告下载。当需要查询 APP UI 自动化资源、执行 APP 测试、管理测试设备或查看执行结果时使用。注意：这是移动端 APP 测试，与 Web UI 自动化（ui-automation）不同。
---

# WHartTest APP UI 自动化管理

## 概述

WHartTest APP UI 自动化模块基于 Airtest/Poco 框架，提供移动端 APP（Android/iOS）的 UI 自动化测试能力。支持 Airtest 脚本管理、测试设备管理、脚本执行、执行报告生成与查看、批量执行等功能。

**与 Web UI 自动化的区别**：APP UI 自动化针对移动端 APP（通过 Airtest 图像识别/Poco 元素定位），而 Web UI 自动化（ui-automation）针对 Web 页面（通过浏览器元素定位）。请勿混淆。

## 生命周期概览

```text
资源准备 -> 脚本上传 -> 设备配置 -> 调试执行 -> 结果查看 -> 批量执行

1. 模块管理（5 级树形结构）
2. 上传 Airtest 脚本（.zip/.air/.py，通过 Web 界面）
3. 注册测试设备（ADB TCP/模拟器/云真机/USB）
4. 单脚本调试执行 + 设备连接检测
5. 查看执行记录、步骤统计、HTML 报告
6. 批量执行（定时任务/API 触发）
```

## 关键原则

- **脚本上传仅限 Web 界面**：Airtest 脚本涉及文件上传（.zip/.air/.py），需通过 WHartTest 平台 Web 界面上传，工具脚本不支持创建脚本。
- **先检测后执行**：执行脚本前，优先用 `check_device` 检测设备连接状态，避免因设备离线导致执行失败。
- **执行是异步的**：`execute_script` 发起异步执行后立即返回执行记录 ID，需轮询 `get_execution_record` 查看最终状态。
- **全局执行配置**：图像匹配阈值、查找超时等参数通过 `get_execution_config` / `update_execution_config` 统一管理，修改后对后续执行生效。

## 快速开始

```bash
# 基本调用
python app_ui_automation_tools.py --action <action_name> --project_id <project_id>

# 带请求体
python app_ui_automation_tools.py --action create_module --project_id 1 --payload '{"name":"登录模块"}'

# 从文件读取 JSON
python app_ui_automation_tools.py --action update_device --project_id 1 --device_id 5 --payload @device.json

# 带查询参数
python app_ui_automation_tools.py --action list_scripts --project_id 1 --params '{"module":10,"platform":"android","page":1}'
```

## 常用枚举值

### 脚本平台

- `android` - Android 平台
- `ios` - iOS 平台

### 脚本状态

- `idle` - 空闲
- `running` - 执行中
- `success` - 成功
- `failed` - 失败

### 脚本等级

- `P0` - 最高优先级
- `P1`
- `P2`
- `P3` - 最低优先级

### 设备连接类型

- `adb_tcp` - ADB TCP 远程连接
- `emulator` - Android 模拟器
- `cloud` - 云真机平台
- `usb` - USB 直连

### 设备状态

- `online` - 在线
- `offline` - 离线
- `busy` - 忙碌

### 执行记录状态（数字）

- `0` - 等待中
- `1` - 执行中
- `2` - 成功
- `3` - 失败
- `4` - 取消

### 执行触发类型

- `manual` - 手动触发
- `scheduled` - 定时触发
- `api` - API 触发
- `debug` - 调试执行

### 批量执行状态（数字）

- `0` - 待执行
- `1` - 执行中
- `2` - 全部成功
- `3` - 部分失败
- `4` - 全部失败

## 可用动作

### 模块管理

| Action | 说明 |
|---|---|
| `list_modules` | 列出模块（支持按 project/parent/level 过滤） |
| `get_module` | 获取模块详情 |
| `create_module` | 创建模块 |
| `update_module` | 更新模块 |
| `delete_module` | 删除模块（存在关联脚本时无法删除） |
| `get_module_tree` | 获取模块树形结构 |

### 脚本管理

> **注意**：脚本创建需通过 Web 界面上传文件（.zip/.air/.py），工具脚本不支持 `create_script`。

| Action | 说明 |
|---|---|
| `list_scripts` | 列出脚本（支持按 project/module/platform/status 过滤） |
| `get_script` | 获取脚本详情 |
| `update_script` | 更新脚本信息（名称、描述、等级、平台等） |
| `delete_script` | 删除脚本（同时清理脚本文件） |
| `preview_script` | 预览脚本源码（返回入口 .py 文件内容） |
| `execute_script` | 执行单个脚本（调试模式，异步返回执行记录 ID） |

### 设备管理

| Action | 说明 |
|---|---|
| `list_devices` | 列出设备（支持按 project/platform/connection_type/status 过滤） |
| `get_device` | 获取设备详情 |
| `create_device` | 创建设备 |
| `update_device` | 更新设备 |
| `delete_device` | 删除设备 |
| `check_device` | 检测设备连接状态（返回 online/offline） |

### 执行记录

| Action | 说明 |
|---|---|
| `list_execution_records` | 列出执行记录（支持按 script/device/status/trigger_type 过滤） |
| `get_execution_record` | 获取执行记录详情（含步骤统计、错误信息、执行时长） |
| `delete_execution_record` | 删除执行记录 |
| `cancel_execution` | 取消执行中的任务 |

### 批量执行记录

| Action | 说明 |
|---|---|
| `list_batch_records` | 列出批量执行记录（支持按 status/trigger_type 过滤） |
| `get_batch_record` | 获取批量执行记录详情（含成功/失败统计） |

### 执行配置（全局单例）

| Action | 说明 |
|---|---|
| `get_execution_config` | 获取全局执行配置 |
| `update_execution_config` | 更新执行配置（阈值、超时、延迟等） |

## 常见 Payload 结构

### 创建模块

```json
{
    "name": "登录模块",
    "parent": null
}
```

### 创建设备

```json
{
    "name": "测试机-小米12",
    "connection_type": "adb_tcp",
    "platform": "android",
    "device_uri": "android://127.0.0.1:5037/序列号",
    "device_serial": "序列号",
    "description": "小米12 测试设备",
    "is_default": false
}
```

### 更新脚本

```json
{
    "name": "登录测试脚本",
    "description": "验证登录功能",
    "level": "P1",
    "platform": "android"
}
```

### 执行脚本

```json
{
    "device_id": 5,
    "trigger_type": "debug"
}
```

### 更新执行配置

```json
{
    "airtest_threshold": 0.7,
    "airtest_find_timeout": 20,
    "airtest_opdelay": 1.0,
    "poco_wait_timeout": 15
}
```

## 使用示例

### 1. 获取模块树

```bash
python app_ui_automation_tools.py --action get_module_tree --project_id 1
```

### 2. 创建设备并检测连接

```bash
python app_ui_automation_tools.py --action create_device --project_id 1 --payload @device.json
python app_ui_automation_tools.py --action check_device --project_id 1 --device_id 5
```

### 3. 查询脚本并预览源码

```bash
python app_ui_automation_tools.py --action list_scripts --project_id 1 --params '{"module":10,"platform":"android"}'
python app_ui_automation_tools.py --action preview_script --project_id 1 --script_id 3
```

### 4. 执行脚本并查看结果

```bash
# 发起调试执行
python app_ui_automation_tools.py --action execute_script --project_id 1 --script_id 3 --payload '{"device_id":5,"trigger_type":"debug"}'

# 查看执行记录（status: 0=等待 1=执行中 2=成功 3=失败 4=取消）
python app_ui_automation_tools.py --action get_execution_record --project_id 1 --record_id 88

# 查看历史执行记录
python app_ui_automation_tools.py --action list_execution_records --project_id 1 --params '{"script":3,"status":2}'
```

### 5. 取消执行中的任务

```bash
python app_ui_automation_tools.py --action get_execution_record --project_id 1 --record_id 88
python app_ui_automation_tools.py --action cancel_execution --project_id 1 --record_id 88
```

### 6. 查看批量执行记录

```bash
python app_ui_automation_tools.py --action list_batch_records --project_id 1 --params '{"status":2}'
python app_ui_automation_tools.py --action get_batch_record --project_id 1 --batch_id 12
```

### 7. 查看和更新执行配置

```bash
python app_ui_automation_tools.py --action get_execution_config --project_id 1
python app_ui_automation_tools.py --action update_execution_config --project_id 1 --payload '{"airtest_threshold":0.7}'
```

## 执行配置参数说明

| 参数 | 说明 | 默认值 |
|---|---|---|
| `airtest_threshold` | 图像匹配阈值（0-1，值越低匹配越宽松） | 0.6 |
| `airtest_find_timeout` | 元素查找超时（秒） | 30 |
| `airtest_opdelay` | 操作间隔延迟（秒） | 1.0 |
| `poco_wait_timeout` | Poco 元素等待超时（秒，修改后需重新连接设备才生效） | 20 |

## 故障排查

| 问题 | 处理建议 |
|---|---|
| `401 Unauthorized` / `403 Forbidden` | 检查 `--api_key` 是否正确，确认用户对项目有权限 |
| `404 Not Found` | 检查 `project_id` 和各类资源 ID 是否正确 |
| 设备连接失败 | 用 `check_device` 检测设备状态，确认设备 URI 格式正确 |
| 脚本执行失败 | 用 `get_execution_record` 查看 `error_message` 和步骤统计 |
| 执行卡住 | 用 `get_execution_record` 查看状态，必要时 `cancel_execution` |
| 图像识别失败 | 用 `get_execution_config` 检查阈值，适当调低 `airtest_threshold` |
| Poco 元素找不到 | 检查 `poco_wait_timeout` 是否足够，注意修改后需重连设备 |
| 删除模块失败 | 模块下存在关联脚本，需先删除或迁移脚本 |

## 建议工作流

1. `get_module_tree` 了解项目模块结构
2. `list_scripts` 查看已有脚本，`preview_script` 查看脚本源码
3. `list_devices` / `check_device` 确认可用设备
4. `execute_script` 发起调试执行
5. `get_execution_record` 轮询执行状态，查看步骤统计和错误信息
6. 执行失败时检查 `error_message`，必要时调整 `update_execution_config`
7. 执行成功后可通过 Web 界面查看 HTML 报告
