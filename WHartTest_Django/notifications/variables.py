"""变量注册表与上下文构建"""
from django.utils import timezone


# 变量列表：(变量名, 说明, 示例值)
VARIABLES = [
    ('task_name', '任务名称', '登录模块回归测试'),
    ('project_name', '项目名称', 'J&T Express'),
    ('status', '执行状态', '成功 / 失败'),
    ('trigger_type', '触发方式', '定时 / 手动 / API'),
    ('total', '用例总数', '15'),
    ('passed', '通过数', '13'),
    ('failed', '失败数', '2'),
    ('pass_rate', '通过率', '86.7%'),
    ('duration', '执行时长', '5分23秒'),
    ('executor', '执行人', 'admin'),
    ('failed_cases', '失败用例列表', 'test_login / test_payment'),
    ('error_summary', '错误摘要', '2个用例执行失败'),
    ('current_date', '当前日期时间', '2026-07-14 15:30:00'),
    ('report_url', '报告链接', 'https://...'),
    ('task_url', '任务详情链接', 'https://...'),
    ('platform_name', '平台名称', 'WHartTest'),
]


def render_content(content: str, context: dict) -> str:
    """简单字符串替换：将 {{key}} 替换为 context[key]"""
    for key, value in context.items():
        content = content.replace(f'{{{{{key}}}}}', str(value))
    return content


def _format_duration(seconds):
    """将秒数格式化为可读时长"""
    if seconds is None:
        return '-'
    total = int(seconds)
    if total < 60:
        return f'{total}秒'
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f'{minutes}分{secs}秒'
    hours, mins = divmod(minutes, 60)
    return f'{hours}小时{mins}分{secs}秒'


def build_context(task, execution, module_result):
    """根据任务模块类型构建变量上下文字典"""
    from task_center.models import ScheduledTask

    context = {
        'task_name': task.name,
        'project_name': task.project.name if task.project else '',
        'trigger_type': execution.get_trigger_type_display() if execution else '',
        'current_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'platform_name': 'WHartTest',
        'total': 0,
        'passed': 0,
        'failed': 0,
        'pass_rate': '0%',
        'duration': '-',
        'executor': '',
        'failed_cases': '无',
        'error_summary': '',
        'report_url': '',
        'task_url': '',
    }

    if execution:
        if execution.status == 'success':
            context['status'] = '成功'
        elif execution.status == 'failed':
            context['status'] = '失败'
        else:
            context['status'] = execution.status

        if execution.started_at and execution.finished_at:
            delta = (execution.finished_at - execution.started_at).total_seconds()
            context['duration'] = _format_duration(delta)

        if execution.task and execution.task.creator:
            context['executor'] = execution.task.creator.username
    else:
        context['status'] = '未知'

    # 根据模块类型提取统计数据
    if task.module == ScheduledTask.TaskModule.APP_UI_AUTOMATION and module_result:
        _fill_app_ui_context(context, module_result, execution)
    elif task.module == ScheduledTask.TaskModule.UI_AUTOMATION:
        _fill_ui_automation_context(context, task)
    elif task.module == ScheduledTask.TaskModule.TEST_SUITE:
        _fill_test_suite_context(context, task)

    return context


def _fill_app_ui_context(context, batch, execution):
    """从 AppUiBatchExecutionRecord 提取统计数据"""
    context['total'] = batch.total_scripts
    context['passed'] = batch.passed_scripts
    context['failed'] = batch.failed_scripts

    if batch.total_scripts > 0:
        rate = round(batch.passed_scripts / batch.total_scripts * 100, 1)
        context['pass_rate'] = f'{rate}%'

    if batch.duration:
        context['duration'] = _format_duration(batch.duration)

    if batch.failed_scripts > 0:
        failed_records = batch.execution_records.filter(status=3).select_related('script')
        failed_names = [r.script.name for r in failed_records if r.script]
        context['failed_cases'] = ' / '.join(failed_names) if failed_names else '无'
        context['error_summary'] = f'{batch.failed_scripts}个脚本执行失败'
    else:
        context['failed_cases'] = '无'
        context['error_summary'] = ''

    if batch.id:
        context['report_url'] = f'/app-ui-automation/batch-records/{batch.id}/'
    if execution and execution.task and execution.task.id:
        context['task_url'] = f'/task-center?task={execution.task.id}'


def _fill_ui_automation_context(context, task):
    """从 UI 自动化执行记录提取统计数据"""
    from ui_automation.models import UiBatchExecutionRecord
    batch_name = f"定时任务-{task.name}"
    batches = UiBatchExecutionRecord.objects.filter(name=batch_name).order_by('-created_at')
    if batches.exists():
        batch = batches.first()
        context['total'] = getattr(batch, 'total_cases', 0) or 0
        context['passed'] = getattr(batch, 'passed_cases', 0) or 0
        context['failed'] = getattr(batch, 'failed_cases', 0) or 0
        total = context['total']
        if total > 0:
            rate = round(context['passed'] / total * 100, 1)
            context['pass_rate'] = f'{rate}%'
        if context['failed'] > 0:
            context['error_summary'] = f'{context["failed"]}个用例执行失败'
    if task.id:
        context['task_url'] = f'/task-center?task={task.id}'


def _fill_test_suite_context(context, task):
    """从测试套件执行记录提取统计数据"""
    from testcases.models import TestExecution
    if task.test_suite:
        executions = TestExecution.objects.filter(suite=task.test_suite).order_by('-id')
        if executions.exists():
            exec_record = executions.first()
            total = exec_record.testcaseresult_set.count() if hasattr(exec_record, 'testcaseresult_set') else 0
            passed = exec_record.testcaseresult_set.filter(status='pass').count() if total else 0
            failed = exec_record.testcaseresult_set.filter(status='fail').count() if total else 0
            context['total'] = total
            context['passed'] = passed
            context['failed'] = failed
            if total > 0:
                rate = round(passed / total * 100, 1)
                context['pass_rate'] = f'{rate}%'
            if failed > 0:
                context['error_summary'] = f'{failed}个用例执行失败'
    if task.id:
        context['task_url'] = f'/task-center?task={task.id}'
