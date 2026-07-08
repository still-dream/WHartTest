# APPUI 自动化功能模块 — 设计规格

> 日期: 2026-07-08
> 状态: 已批准（待用户最终审查）
> 基于: brainstorming skill 流程产出

---

## 1. 概述

### 1.1 模块定位

APPUI 自动化模块是基于 Airtest 框架的 APP 端 UI 自动化测试能力，与现有 Web UI 自动化模块（`ui_automation`，基于 Playwright）平行独立。

### 1.2 核心能力

- 上传 AirtestIDE 录制的 `.air` 格式脚本（zip 包）
- 选择执行环境（设备）并执行脚本调试
- 自动生成标准格式测试报告（Standalone HTML，自定义品牌模板）
- 支持设置 APPUI 自动化的定时任务（多脚本串行执行）
- 在线查看每次运行的测试报告
- 测试报告支持下载

### 1.3 关键决策摘要

| 决策点 | 选择 | 说明 |
|--------|------|------|
| 执行架构 | 混合方案 | airtest Python 库执行脚本 + AirtestIDE reporter 生成报告 |
| 部署环境 | Docker 容器 | Django 与 AirtestIDE 在同一容器，AirtestIDE 仅用于报告生成 |
| 设备连接 | 多种混合 | 支持 ADB TCP / 模拟器 / 云真机 / USB 直连 |
| 脚本组织 | 模块树 + 脚本 | 5 级模块树，脚本挂在模块下，无套件 |
| 定时任务 | 复用 task_center | 多脚本串行执行 |
| 报告生成 | reporter + 自定义模板 | AirtestIDE reporter + log_template.html + pack_html() |
| 执行引擎架构 | 轻量集成式 | Celery 异步任务 + 服务类，前端轮询状态 |

---

## 2. 架构概览

### 2.1 新建 Django App

新建 `app_ui_automation` 应用，注册到 `INSTALLED_APPS`，URL 前缀 `api/app-ui-automation/`。

### 2.2 架构图

```
┌─────────────────────────────────────────────────────────┐
│  前端 Vue (features/app-ui-automation/)                  │
│  模块树 │ 脚本管理 │ 设备管理 │ 执行记录 │ 报告查看       │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP API
┌──────────────────────▼──────────────────────────────────┐
│  Django App: app_ui_automation                           │
│  ├── models.py    (AppUiModule, AppUiScript, AppUiDevice │
│  │                 AppUiExecutionRecord, AppUiBatchRecord)│
│  ├── executor.py  (执行引擎服务类)                        │
│  │   ├── airtest Python 库执行脚本                        │
│  │   ├── airtest reporter 生成报告（自定义模板）           │
│  │   ├── pack_html() 打包 Standalone HTML                 │
│  │   └── parse_log() 解析步骤统计                         │
│  ├── tasks.py     (Celery 异步任务)                       │
│  ├── views.py     (DRF ViewSet)                          │
│  ├── serializers.py                                      │
│  └── urls.py                                            │
└──────────────────────┬──────────────────────────────────┘
                       │ Celery Task
┌──────────────────────▼──────────────────────────────────┐
│  Celery Worker (Docker 容器内)                           │
│  ├── airtest Python 库 (执行脚本)                        │
│  ├── AirtestIDE CLI (仅 reporter 用于报告生成)            │
│  └── 自定义报告模板 (复用 testcases/appuitest/ 模板)      │
└─────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  task_center (现有模块扩展)                               │
│  └── TaskModule 新增 'app_ui_automation'                 │
│      └── 多脚本串行执行                                   │
└─────────────────────────────────────────────────────────┘
```

### 2.3 设计原则

1. **脚本即用例** — 一个 `.air` 脚本就是一个完整测试用例，无需拆分步骤
2. **文件存储** — 脚本 zip 和报告 HTML 存储在 MEDIA_ROOT 下，DB 只存路径
3. **串行执行** — 多脚本定时任务串行执行，一个完成再执行下一个
4. **复用现有管线** — 直接复用 `testcases/appuitest/log_untitled/run_all.py` 的 `pack_html()` 函数和报告模板

---

## 3. 数据模型

### 3.1 模型关系

```
Project
  ├── AppUiModule (5级树形)
  │     └── AppUiScript (上传的 .air 脚本)
  │           └── AppUiExecutionRecord (执行记录)
  │                 ├── report_path (Standalone HTML)
  │                 └── log_dir (原始日志)
  └── AppUiDevice (设备管理，多种连接类型)
```

### 3.2 AppUiModule — 模块管理

与现有 `UiModule` 设计一致，支持 5 级树形子模块。

字段：
- `project` (FK → Project, CASCADE)
- `name` (CharField, max_length=100)
- `parent` (FK → self, CASCADE, null=True, blank=True)
- `level` (PositiveSmallIntegerField, default=1, 最大5级)
- `creator` (FK → User, SET_NULL, null=True)
- `created_at` / `updated_at` (DateTimeField)

约束：`unique_together = ('project', 'parent', 'name')`，`db_table = 'app_ui_module'`

### 3.3 AppUiScript — Airtest 脚本

字段：
- `project` (FK → Project, CASCADE)
- `module` (FK → AppUiModule, PROTECT)
- `name` (CharField, max_length=255)
- `description` (TextField, blank=True, null=True)
- `platform` (CharField, choices=[('android','Android'),('ios','iOS')], default='android')
- `script_file` (FileField, upload_to=`app_ui_scripts/{project_id}/{script_id}/`) — 上传的 zip 包
- `script_dir` (CharField, max_length=500, blank=True, default='') — 解压后目录路径（相对 MEDIA_ROOT）
- `script_entry` (CharField, max_length=255, blank=True, default='') — 脚本入口文件名（自动识别）
- `level` (CharField, choices=P0/P1/P2/P3, default='P2')
- `status` (CharField, choices=[('idle','空闲'),('running','执行中'),('success','成功'),('failed','失败')], default='idle')
- `creator` (FK → User, SET_NULL, null=True)
- `created_at` / `updated_at`

约束：`db_table = 'app_ui_script'`

上传流程：用户上传 `.air` 目录的 zip → 后端解压 → 自动识别与 `.air` 同名的 `.py` 入口文件 → 存储 `script_dir` 和 `script_entry`

### 3.4 AppUiDevice — 设备管理

字段：
- `project` (FK → Project, CASCADE)
- `name` (CharField, max_length=100) — 如：测试机-小米12
- `connection_type` (CharField, choices=[('adb_tcp','ADB TCP 远程'),('emulator','Android 模拟器'),('cloud','云真机平台'),('usb','USB 直连')], default='adb_tcp')
- `platform` (CharField, choices=[('android','Android'),('ios','iOS')], default='android')
- `device_uri` (CharField, max_length=500) — Airtest 设备连接 URI
- `device_serial` (CharField, max_length=255, blank=True, default='') — 设备序列号
- `status` (CharField, choices=[('online','在线'),('offline','离线'),('busy','忙碌')], default='offline')
- `description` (TextField, blank=True, null=True)
- `is_default` (BooleanField, default=False)
- `creator` (FK → User, SET_NULL, null=True)
- `created_at` / `updated_at`

约束：`unique_together = ('project', 'name')`，`db_table = 'app_ui_device'`

`device_uri` 格式参考：
- ADB TCP: `android://127.0.0.1:5037/118f492e?cap_method=MINICAP&&ori_method=MINICAPORI&&touch_method=MINITOUCH`
- 模拟器: `android://127.0.0.1:5037/emulator-5554`
- iOS: `ios:///127.0.0.1:8100`

### 3.5 AppUiExecutionRecord — 执行记录

字段：
- `batch` (FK → AppUiBatchExecutionRecord, CASCADE, null=True, blank=True)
- `script` (FK → AppUiScript, CASCADE)
- `device` (FK → AppUiDevice, SET_NULL, null=True, blank=True)
- `status` (SmallIntegerField, choices=[(0,'等待中'),(1,'执行中'),(2,'成功'),(3,'失败'),(4,'取消')], default=0)
- `trigger_type` (CharField, choices=[('manual','手动'),('scheduled','定时'),('api','API'),('debug','调试')], default='manual')
- `executor` (FK → User, SET_NULL, null=True)
- `total_steps` (IntegerField, default=0)
- `passed_steps` (IntegerField, default=0)
- `failed_steps` (IntegerField, default=0)
- `report_path` (CharField, max_length=500, blank=True, default='') — Standalone HTML 路径（相对 MEDIA_ROOT）
- `log_dir` (CharField, max_length=500, blank=True, default='') — 原始日志目录路径
- `execution_log` (TextField, blank=True, null=True)
- `error_message` (TextField, null=True, blank=True)
- `start_time` (DateTimeField, null=True, blank=True)
- `end_time` (DateTimeField, null=True, blank=True)
- `duration` (FloatField, null=True, blank=True) — 执行时长（秒）
- `celery_task_id` (CharField, max_length=255, blank=True, default='')
- `created_at` (DateTimeField, auto_now_add=True)

约束：`db_table = 'app_ui_execution_record'`

### 3.6 AppUiBatchExecutionRecord — 批量执行记录

用于定时任务的多脚本串行执行。

字段：
- `name` (CharField, max_length=255)
- `total_scripts` (IntegerField, default=0)
- `passed_scripts` (IntegerField, default=0)
- `failed_scripts` (IntegerField, default=0)
- `status` (SmallIntegerField, choices=[(0,'待执行'),(1,'执行中'),(2,'全部成功'),(3,'部分失败'),(4,'全部失败')], default=0)
- `trigger_type` (CharField, choices=[('manual','手动'),('scheduled','定时'),('api','API')], default='manual')
- `executor` (FK → User, SET_NULL, null=True)
- `start_time` / `end_time` (DateTimeField, null=True, blank=True)
- `duration` (FloatField, null=True, blank=True) — 总时长（秒）
- `created_at` (DateTimeField, auto_now_add=True)

约束：`db_table = 'app_ui_batch_execution_record'`

`update_statistics()` 方法：遍历 `execution_records`，更新 passed/failed 计数和批次状态。

---

## 4. API 设计

### 4.1 路由注册

在 `wharttest_django/urls.py` 中新增：
```python
path("api/app-ui-automation/", include("app_ui_automation.urls")),
```

### 4.2 接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| **模块管理** | | |
| GET | `/modules/` | 模块列表（支持 project/parent 过滤） |
| GET | `/modules/tree/` | 模块树（按项目） |
| POST | `/modules/` | 创建模块 |
| PATCH | `/modules/{id}/` | 更新模块 |
| DELETE | `/modules/{id}/` | 删除模块 |
| **脚本管理** | | |
| GET | `/scripts/` | 脚本列表（支持 project/module/search 过滤） |
| POST | `/scripts/` | 创建脚本（含上传 zip） |
| GET | `/scripts/{id}/` | 脚本详情 |
| PATCH | `/scripts/{id}/` | 更新脚本信息 |
| DELETE | `/scripts/{id}/` | 删除脚本（同时删除文件） |
| GET | `/scripts/{id}/preview/` | 预览脚本 .py 源码 |
| POST | `/scripts/{id}/execute/` | 执行单个脚本（调试） |
| **设备管理** | | |
| GET | `/devices/` | 设备列表 |
| POST | `/devices/` | 添加设备 |
| PATCH | `/devices/{id}/` | 更新设备 |
| DELETE | `/devices/{id}/` | 删除设备 |
| POST | `/devices/{id}/check/` | 检测设备连接状态 |
| **执行记录** | | |
| GET | `/execution-records/` | 执行记录列表 |
| GET | `/execution-records/{id}/` | 执行记录详情 |
| DELETE | `/execution-records/{id}/` | 删除执行记录 |
| GET | `/execution-records/{id}/report/` | 在线查看报告（返回 HTML） |
| GET | `/execution-records/{id}/download/` | 下载报告（返回文件流） |
| POST | `/execution-records/{id}/cancel/` | 取消执行中任务 |
| **批量记录** | | |
| GET | `/batch-records/` | 批量执行记录列表 |
| GET | `/batch-records/{id}/` | 批量执行记录详情 |

### 4.3 核心接口详情

**执行脚本（调试）：** `POST /scripts/{id}/execute/`
```json
// 请求
{ "device_id": 1, "trigger_type": "debug" }
// 响应
{ "id": 123, "status": 1, "celery_task_id": "abc-123", "message": "脚本已开始执行" }
```

**在线查看报告：** `GET /execution-records/{id}/report/`
```python
# 返回 Standalone HTML，前端用新窗口/iframe 打开
return FileResponse(open(html_path, 'rb'), content_type='text/html')
```

**下载报告：** `GET /execution-records/{id}/download/`
```python
# 返回文件流，浏览器触发下载
filename = f"{record.script.name}_{record.created_at:%Y%m%d_%H%M%S}.html"
response['Content-Disposition'] = f'attachment; filename="{filename}"'
```

**取消执行：** `POST /execution-records/{id}/cancel/`
```python
# 通过 celery_task_id 撤销 Celery 任务
app.control.revoke(record.celery_task_id, terminate=True)
record.status = 4  # 取消
record.save()
```

---

## 5. 执行引擎

### 5.1 执行流程

```
用户发起执行
    │
    ▼
1. 创建 ExecutionRecord (status=1 执行中)
    │
    ▼
2. STEP 1: Run Script — airtest Python 库执行
   - connect_device(device_uri)
   - set_logdir(log_dir)
   - exec(script_content)  → 写 log.txt + 截图到 log_dir
    │
    ▼
3. STEP 2: Generate Report — AirtestIDE CLI reporter
   - airtest reporter --log_root LOG_DIR --export REPORT_DIR
   - 用 log_template.html 覆盖默认模板样式
    │
    ▼
4. STEP 3: Pack HTML — 复用 run_all.py 的 pack_html()
   - 内联所有 CSS/JS/图片资源为单个 Standalone HTML
    │
    ▼
5. Parse log.txt — 解析 JSON-lines 日志
   - 统计 total_steps / passed_steps / failed_steps
    │
    ▼
6. 更新 ExecutionRecord (status=2/3, report_path, 统计)
```

### 5.2 执行引擎实现

新建 `app_ui_automation/executor.py`：

```python
class AppUiScriptExecutor:
    """APPUI 脚本执行引擎"""

    def execute(self, execution_record_id):
        record = AppUiExecutionRecord.objects.get(id=execution_record_id)
        script = record.script
        device = record.device

        # 1. 准备工作目录
        work_dir = self._prepare_work_dir(record)
        log_dir = work_dir / "log"
        report_dir = work_dir / "report"
        standalone_dir = work_dir / "standalone"

        try:
            # 2. STEP 1: 用 airtest Python 库执行脚本
            self._run_script_with_airtest(script, device, log_dir)

            # 3. STEP 2: 用 AirtestIDE reporter 生成报告（自定义模板）
            html_dir = self._generate_report(script, log_dir, report_dir)

            # 4. STEP 3: 打包 Standalone HTML（复用 pack_html）
            standalone_path = self._pack_html(html_dir, standalone_dir)

            # 5. 解析日志统计
            stats = self._parse_log_stats(log_dir)

            # 6. 更新记录
            record.report_path = str(standalone_path.relative_to(MEDIA_ROOT))
            record.total_steps = stats['total']
            record.passed_steps = stats['passed']
            record.failed_steps = stats['failed']
            record.status = 2 if stats['failed'] == 0 else 3

        except Exception as e:
            record.status = 3  # 失败
            record.error_message = str(e)
        finally:
            record.end_time = timezone.now()
            record.duration = (record.end_time - record.start_time).total_seconds()
            record.save()
```

### 5.3 STEP 1: airtest Python 库执行

```python
def _run_script_with_airtest(self, script, device, log_dir):
    from airtest.core.api import connect_device, set_logdir

    # 设置日志目录
    set_logdir(str(log_dir))

    # 连接设备
    connect_device(device.device_uri)

    # 执行脚本
    script_path = os.path.join(MEDIA_ROOT, script.script_dir, script.script_entry)
    with open(script_path, 'r', encoding='utf-8') as f:
        script_content = f.read()

    # 设置 __file__ 变量使 Template 图片路径正确
    script_globals = {'__file__': script_path}
    exec(compile(script_content, script_path, 'exec'), script_globals)
```

### 5.4 STEP 2: 报告生成（自定义模板）

```python
def _generate_report(self, script, log_dir, report_dir):
    import subprocess
    script_path = os.path.join(MEDIA_ROOT, script.script_dir)

    cmd = [
        settings.AIRTEST_IDE_PATH, "reporter",
        script_path,
        "--log_root", str(log_dir),
        "--lang", settings.AIRTEST_REPORT_LANG,
        "--export", str(report_dir),
    ]
    subprocess.run(cmd, check=True)

    # 用自定义模板覆盖默认报告样式
    self._apply_custom_template(report_dir)

    return report_dir / f"{script.script_entry.replace('.py', '')}.log"
```

### 5.5 STEP 3: 打包 Standalone HTML

直接复用 `testcases/appuitest/log_untitled/run_all.py` 中的 `pack_html()` 函数。该函数将 log.html + CSS + JS + 图片资源内联为单个 HTML 文件。

### 5.6 日志解析

Airtest 的 `log.txt` 是 JSON-lines 格式，每行一个 JSON 对象：
```json
{"tag": "function", "depth": 1, "data": {"name": "touch", "call_args": {...}, "ret": [317, 801]}}
{"tag": "function", "depth": 1, "data": {"name": "assert_exists", "call_args": {...}}}
```

解析逻辑：
- 遍历 `depth == 1` 的行（顶层操作）
- `name` 为 `touch`/`swipe`/`wait`/`text`/`keyevent` → 操作步骤
- `name` 为 `assert_exists`/`assert_not_exists` → 断言步骤
- 含 `traceback` 或 `tag == "error"` → 失败步骤
- 汇总 total/passed/failed

### 5.7 Celery 任务

`app_ui_automation/tasks.py`：

```python
@shared_task
def execute_app_ui_script(execution_record_id):
    """执行单个 APPUI 脚本"""
    executor = AppUiScriptExecutor()
    executor.execute(execution_record_id)

@shared_task
def execute_app_ui_batch(batch_record_id, script_ids, device_id):
    """串行执行多个脚本（定时任务）"""
    batch = AppUiBatchExecutionRecord.objects.get(id=batch_record_id)
    for script_id in script_ids:
        record = AppUiExecutionRecord.objects.create(
            batch=batch, script_id=script_id, device_id=device_id,
            trigger_type='scheduled', ...
        )
        execute_app_ui_script(record.id)  # 同步串行调用
    batch.update_statistics()
```

### 5.8 文件存储结构

```
MEDIA_ROOT/
  app_ui_scripts/                    # 脚本文件
    {project_id}/
      {script_id}/
        untitled.air/                # 解压后的 .air 目录
          untitled.py
          tpl1234567890.png
          ...
  app_ui_reports/                    # 执行报告
    {project_id}/
      {execution_record_id}/
        log/
          log.txt                    # 原始日志
          1782453106607.jpg          # 截图
        report/
          untitled.log/              # AirtestIDE 生成的报告
            log.html
            static/
        standalone/
          {timestamp}.html           # 最终 Standalone HTML
```

### 5.9 配置项

在 `settings.py` 中新增：

```python
# AirtestIDE 配置（仅用于报告生成）
AIRTEST_IDE_PATH = os.environ.get('AIRTEST_IDE_PATH',
    r'C:\Program Files\AirtestIDE-win-1.2.17\AirtestIDE\AirtestIDE')
AIRTEST_REPORT_LANG = 'zh'
# 自定义报告模板路径
AIRTEST_REPORT_TEMPLATE = os.path.join(BASE_DIR, 'testcases', 'appuitest', 'log_template.html')
```

---

## 6. 定时任务集成

### 6.1 复用 task_center

在 `task_center/models.py` 的 `ScheduledTask.TaskModule` 中新增：

```python
class TaskModule(models.TextChoices):
    UI_AUTOMATION = 'ui_automation', _('UI 自动化')
    TEST_SUITE = 'test_suite', _('测试套件')
    APP_UI_AUTOMATION = 'app_ui_automation', _('APPUI 自动化')  # 新增
```

### 6.2 ScheduledTask 扩展字段

```python
app_ui_scripts = models.ManyToManyField(
    'app_ui_automation.AppUiScript', blank=True,
    related_name='scheduled_tasks',
    verbose_name=_('关联APPUI脚本'),
    help_text=_('模块为"APPUI自动化"时选择要执行的脚本（串行执行）')
)
app_ui_device = models.ForeignKey(
    'app_ui_automation.AppUiDevice', on_delete=models.SET_NULL,
    null=True, blank=True, related_name='scheduled_tasks',
    verbose_name=_('执行设备'),
    help_text=_('APPUI自动化执行时使用的设备')
)
```

### 6.3 调度执行逻辑

在 `task_center/tasks.py` 的 `execute_scheduled_task` 中新增分支：

```python
if task.module == ScheduledTask.TaskModule.APP_UI_AUTOMATION:
    scripts = task.app_ui_scripts.all()
    batch = AppUiBatchExecutionRecord.objects.create(
        name=f"定时任务-{task.name}",
        total_scripts=scripts.count(),
        trigger_type='scheduled',
        start_time=timezone.now(),
    )
    for script in scripts:
        record = AppUiExecutionRecord.objects.create(
            batch=batch, script=script, device=task.app_ui_device,
            trigger_type='scheduled', status=0,
        )
        execute_app_ui_script(record.id)  # 串行执行
    batch.update_statistics()
```

### 6.4 重试策略

复用现有 `ScheduledTask` 的重试配置（`retry_enabled` / `retry_count` / `retry_interval`）：
- 单脚本执行失败时，按配置重试
- 重试间隔分钟数后重新执行该脚本

### 6.5 前端交互

在任务中心页面"所属模块"下拉框新增"APPUI 自动化"选项，选中后显示：
- 执行设备下拉框（选择 AppUiDevice）
- 关联脚本多选框（选择 AppUiScript 列表）
- 提示文字："多个脚本将串行执行，一个完成后再执行下一个"

---

## 7. 前端设计

### 7.1 目录结构

```
WHartTest_Vue/src/features/app-ui-automation/
  ├── api/
  │   └── index.ts          # API 服务
  ├── types/
  │   └── index.ts          # TypeScript 类型定义
  ├── views/
  │   ├── AppUiAutomationView.vue   # 主视图（标签页布局）
  │   ├── ModuleTree.vue            # 模块树
  │   ├── ScriptList.vue            # 脚本列表
  │   ├── ScriptUpload.vue          # 脚本上传对话框
  │   ├── DeviceList.vue            # 设备管理
  │   ├── ExecutionRecordList.vue   # 执行记录列表
  │   ├── BatchRecordList.vue       # 批量执行记录
  │   └── ReportViewer.vue          # 报告查看
  ├── components/
  │   ├── ExecuteDialog.vue         # 执行配置对话框
  │   └── DeviceCheckDialog.vue     # 设备检测对话框
  └── index.ts
```

### 7.2 主页面布局

采用与 `UiAutomationView.vue` 一致的标签页布局：左侧模块树 + 右侧标签页（脚本管理 / 设备管理 / 执行记录 / 批量记录）。

### 7.3 核心交互流程

**上传 .air 脚本：**
1. 用户点击"上传脚本"
2. 弹出对话框：选择模块、输入名称、选择平台/等级、拖拽 zip 上传
3. 后端自动解压、识别入口文件
4. 脚本出现在列表中

**执行脚本（调试）：**
1. 脚本列表点击"执行"
2. 弹出执行配置对话框：选择设备
3. 点击"开始执行"，创建执行记录
4. 跳转到执行记录页面，每 3 秒轮询状态
5. 执行完成后显示"查看报告"和"下载"按钮

**查看报告：**
- 点击"查看报告" → 新标签页打开 Standalone HTML

**下载报告：**
- 点击"下载" → 浏览器下载 `{脚本名}_{时间戳}.html`

### 7.4 前端路由

在 `router/index.ts` 中新增：

```typescript
import AppUiAutomationView from '@/features/app-ui-automation/views/AppUiAutomationView.vue';

// 在 children 中新增
{
  path: 'app-ui-automation',
  name: 'AppUiAutomation',
  component: AppUiAutomationView,
},
```

### 7.5 执行状态轮询

```typescript
const pollExecutionStatus = (recordId: number) => {
  const timer = setInterval(async () => {
    const { data } = await executionRecordApi.get(recordId);
    if (data.status !== 1) {  // 不再执行中
      clearInterval(timer);
    }
  }, 3000);
};
```

---

## 8. 实施阶段

1. **阶段一：基础数据管理** — 创建 Django App，实现 Module/Script/Device 模型 + CRUD API，前端模块树 + 脚本上传 + 设备管理
2. **阶段二：执行引擎** — 实现 executor.py（run → report → pack 管线），Celery 异步任务，日志解析，执行记录管理
3. **阶段三：报告管理** — 在线查看报告接口，报告下载接口，前端报告查看和下载
4. **阶段四：定时任务集成** — 扩展 task_center 模型，实现调度执行逻辑，前端任务中心新增 APPUI 选项
5. **阶段五：批量执行** — 实现批量执行 + 批量记录管理
