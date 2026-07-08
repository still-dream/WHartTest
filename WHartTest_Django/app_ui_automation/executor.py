# -*- coding: utf-8 -*-
"""APPUI 脚本执行引擎

三步管线:
  STEP 1: airtest Python 库执行脚本 -> 写 log.txt
  STEP 2: AirtestIDE reporter 生成 HTML 报告 -> 用自定义模板
  STEP 3: pack_html() 打包 Standalone HTML -> 内联所有资源
"""

import os
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from .models import AppUiExecutionRecord


class AppUiScriptExecutor:
    """APPUI 脚本执行引擎"""

    def execute(self, execution_record_id):
        """执行脚本主入口"""
        record = AppUiExecutionRecord.objects.get(id=execution_record_id)
        script = record.script
        device = record.device

        record.status = 1
        record.start_time = timezone.now()
        record.save()

        # 更新脚本状态
        script.status = 'running'
        script.save()

        # 准备工作目录
        work_dir = self._prepare_work_dir(record)
        log_dir = work_dir / "log"
        report_dir = work_dir / "report"
        standalone_dir = work_dir / "standalone"

        try:
            # STEP 1: 用 airtest Python 库执行脚本
            self._run_script_with_airtest(script, device, log_dir)

            # STEP 2: 用 AirtestIDE reporter 生成报告
            html_dir = self._generate_report(script, log_dir, report_dir)

            # STEP 3: 打包 Standalone HTML
            standalone_path = self._pack_html(html_dir, standalone_dir)

            # 解析日志统计
            stats = self._parse_log_stats(log_dir)

            # 更新记录
            record.report_path = str(standalone_path.relative_to(settings.MEDIA_ROOT))
            record.log_dir = str(log_dir.relative_to(settings.MEDIA_ROOT))
            record.total_steps = stats['total']
            record.passed_steps = stats['passed']
            record.failed_steps = stats['failed']
            record.status = 2 if stats['failed'] == 0 else 3

        except Exception as e:
            record.status = 3
            record.error_message = str(e)
            import traceback
            record.execution_log = traceback.format_exc()

        finally:
            record.end_time = timezone.now()
            if record.start_time:
                record.duration = (record.end_time - record.start_time).total_seconds()
            record.save()

            # 更新脚本状态
            script.status = 'success' if record.status == 2 else 'failed'
            script.save()

    def _prepare_work_dir(self, record):
        """准备工作目录"""
        work_dir = Path(settings.MEDIA_ROOT) / 'app_ui_reports' / str(record.script.project.id) / str(record.id)
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir

    def _run_script_with_airtest(self, script, device, log_dir):
        """STEP 1: 使用 airtest Python 库执行脚本"""
        log_dir.mkdir(parents=True, exist_ok=True)

        # 延迟导入 airtest，避免模块加载时依赖
        from airtest.core.api import connect_device, set_logdir

        # 设置日志目录
        set_logdir(str(log_dir))

        # 连接设备
        if device:
            connect_device(device.device_uri)

        # 执行脚本
        script_path = os.path.join(settings.MEDIA_ROOT, script.script_dir, script.script_entry)
        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"脚本文件不存在: {script_path}")

        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()

        # 设置 __file__ 变量使 Template 图片路径正确
        script_globals = {
            '__file__': script_path,
            '__name__': '__main__',
        }
        exec(compile(script_content, script_path, 'exec'), script_globals)

    def _generate_report(self, script, log_dir, report_dir):
        """STEP 2: 使用 AirtestIDE reporter 生成报告"""
        report_dir.mkdir(parents=True, exist_ok=True)
        script_path = os.path.join(settings.MEDIA_ROOT, script.script_dir)

        airtest_exe = getattr(settings, 'AIRTEST_IDE_PATH', 'airtest')
        cmd = [
            airtest_exe, "reporter",
            script_path,
            "--log_root", str(log_dir),
            "--lang", getattr(settings, 'AIRTEST_REPORT_LANG', 'zh'),
            "--export", str(report_dir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"AirtestIDE reporter failed: {result.stderr}")

        # 查找生成的 log.html
        script_name = script.script_entry.replace('.py', '')
        html_dir = report_dir / f"{script_name}.log"
        if not (html_dir / "log.html").is_file():
            # 尝试查找任何包含 log.html 的子目录
            for subdir in report_dir.iterdir():
                if subdir.is_dir() and (subdir / "log.html").is_file():
                    html_dir = subdir
                    break
            else:
                raise FileNotFoundError(f"reporter did not produce log.html in {report_dir}")

        # 应用自定义模板样式
        self._apply_custom_template(html_dir)

        return html_dir

    def _apply_custom_template(self, html_dir):
        """应用自定义报告模板样式（J&T 品牌）"""
        template_path = os.path.join(
            settings.BASE_DIR, 'testcases', 'appuitest', 'log_template.html'
        )
        if not os.path.isfile(template_path):
            return

        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 提取 <style> 块
        style_match = re.search(r'<style>(.*?)</style>', template_content, re.DOTALL)
        if style_match:
            custom_css = style_match.group(1)
            log_html_path = html_dir / "log.html"
            if log_html_path.is_file():
                with open(log_html_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                html = html.replace('</head>', f'<style>{custom_css}</style></head>')
                with open(log_html_path, 'w', encoding='utf-8') as f:
                    f.write(html)

    def _pack_html(self, html_dir, standalone_dir):
        """STEP 3: 打包 Standalone HTML"""
        standalone_dir.mkdir(parents=True, exist_ok=True)

        # 复用 run_all.py 的 pack_html 函数
        run_all_path = os.path.join(
            settings.BASE_DIR, 'testcases', 'appuitest', 'log_untitled'
        )
        if run_all_path not in sys.path:
            sys.path.insert(0, run_all_path)
        from run_all import pack_html

        src = html_dir / "log.html"
        if not src.is_file():
            raise FileNotFoundError(f"log.html not found in {html_dir}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = standalone_dir / f"{timestamp}.html"
        pack_html(src, out_path)
        return out_path

    def _parse_log_stats(self, log_dir):
        """解析 log.txt 统计步骤数"""
        log_file = log_dir / "log.txt"
        stats = {'total': 0, 'passed': 0, 'failed': 0}

        if not log_file.is_file():
            return stats

        operation_names = {'touch', 'swipe', 'wait', 'text', 'keyevent',
                          'sleep', 'assert_exists', 'assert_not_exists',
                          'exists', 'click', 'double_click', 'long_click'}

        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get('depth') == 1:
                        data = entry.get('data', {})
                        name = data.get('name', '')
                        if name in operation_names:
                            stats['total'] += 1
                            if entry.get('tag') == 'error' or 'traceback' in str(data):
                                stats['failed'] += 1
                            else:
                                stats['passed'] += 1
                except json.JSONDecodeError:
                    continue

        return stats
