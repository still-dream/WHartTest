# -*- coding: utf-8 -*-
"""APPUI 脚本执行引擎

三步管线:
  STEP 1: airtest Python 库执行脚本 -> 写 log.txt
  STEP 2: AirtestIDE reporter 生成 HTML 报告 -> 用自定义模板
  STEP 3: pack_html() 打包 Standalone HTML -> 内联所有资源
"""

import os
import json
import logging
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from .models import AppUiExecutionRecord

logger = logging.getLogger(__name__)

_poco_patched = False


def _apply_poco_patch():
    """对 Poco.__init__ 打补丁，使其每次实例化时动态读取最新的 poco_wait_timeout 配置。

    仅打一次补丁，避免重复执行时补丁堆叠（闭包链）和旧 config 对象无法回收。
    """
    global _poco_patched
    if _poco_patched:
        return
    try:
        from poco.pocofw import Poco as _Poco
        _orig_poco_init = _Poco.__init__

        def _patched_poco_init(self, *args, **kwargs):
            _orig_poco_init(self, *args, **kwargs)
            from .models import AppUiExecutionConfig
            config = AppUiExecutionConfig.get_config()
            self._pre_action_wait_for_appearance = config.poco_wait_timeout

        _Poco.__init__ = _patched_poco_init
        _poco_patched = True
    except ImportError:
        pass


class AppUiScriptExecutor:
    """APPUI 脚本执行引擎"""

    def execute(self, execution_record_id):
        """执行脚本主入口"""
        record = AppUiExecutionRecord.objects.get(id=execution_record_id)

        # 如果记录已被取消（revoke 可能未阻止已排队的任务），跳过执行
        if record.status == 4:
            return

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

            # STEP 4: 生成报告截图（用于飞书通知）
            self._generate_screenshot(standalone_path)

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

    def _ensure_device_connected(self, device_uri):
        """对于 TCP 远程设备，先执行 adb connect 确保连接"""
        # URI 格式: android://host:port/serial
        # TCP 设备 serial 为 ip:port 格式，需先 adb connect
        try:
            from urllib.parse import urlparse
            parsed = urlparse(device_uri)
            serial = parsed.path.lstrip('/')
            if ':' in serial:
                subprocess.run(['adb', 'connect', serial],
                               capture_output=True, text=True, timeout=10)
        except Exception:
            pass  # 连接失败不影响后续流程，connect_device 会报具体错误

    def _run_script_with_airtest(self, script, device, log_dir):
        """STEP 1: 使用 airtest Python 库执行脚本"""
        log_dir.mkdir(parents=True, exist_ok=True)

        # 延迟导入 airtest，避免模块加载时依赖
        from airtest.core.api import connect_device, set_logdir
        from airtest.core.settings import Settings as ST

        # 设置日志目录
        set_logdir(str(log_dir))

        # 图像识别参数调优（从数据库读取全局配置）
        from .models import AppUiExecutionConfig
        config = AppUiExecutionConfig.get_config()

        ST.THRESHOLD = config.airtest_threshold
        ST.THRESHOLD_STRICT = config.airtest_threshold
        ST.FIND_TIMEOUT = config.airtest_find_timeout
        ST.OPDELAY = config.airtest_opdelay

        # Poco 元素等待超时调优（monkey-patch 仅执行一次，实例化时动态读取最新配置）
        _apply_poco_patch()

        # 连接设备
        if device:
            self._ensure_device_connected(device.device_uri)
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
        """STEP 2: 生成 HTML 报告"""
        report_dir.mkdir(parents=True, exist_ok=True)
        script_path = os.path.join(settings.MEDIA_ROOT, script.script_dir)

        template_path = getattr(settings, 'AIRTEST_REPORT_TEMPLATE', None)
        has_template = bool(template_path and os.path.isfile(template_path))

        report_generated = False

        # 优先使用 airtest Python API 生成报告（支持自定义模板）
        if has_template:
            try:
                import shutil
                import airtest.report
                # LogToHtml 的 Jinja2 FileSystemLoader 只从 airtest report 包目录查找模板，
                # 需要将自定义模板复制到该目录下，再传文件名
                airtest_report_dir = os.path.dirname(airtest.report.__file__)
                dest_template_name = 'jt_log_template.html'
                dest_template_path = os.path.join(airtest_report_dir, dest_template_name)
                shutil.copy2(template_path, dest_template_path)

                from airtest.report.report import LogToHtml
                rpt = LogToHtml(
                    script_root=script_path,
                    log_root=str(log_dir),
                    export_dir=str(report_dir),
                    lang=getattr(settings, 'AIRTEST_REPORT_LANG', 'zh'),
                )
                rpt.report(template_name=dest_template_name)
                report_generated = True
            except ImportError:
                pass  # airtest Python 包不可用，回退到 CLI
            except Exception as e:
                raise RuntimeError(f"Airtest report failed (Python API): {e}")

        # 回退到 CLI 方式（AirtestIDE 或无自定义模板）
        if not report_generated:
            airtest_exe = getattr(settings, 'AIRTEST_IDE_PATH', 'airtest')
            report_subcmd = 'report' if os.path.basename(airtest_exe) == 'airtest' else 'reporter'
            cmd = [
                airtest_exe, report_subcmd,
                script_path,
                "--log_root", str(log_dir),
                "--lang", getattr(settings, 'AIRTEST_REPORT_LANG', 'zh'),
                "--export", str(report_dir),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Airtest report failed: {result.stderr}")

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

        # 复制 J&T 品牌图片到报告 static/image 目录（确保 pack_html 能内联）
        self._copy_brand_images(html_dir)

        return html_dir

    def _copy_brand_images(self, html_dir):
        """复制 J&T 品牌图片（JT.jpg 背景图、company_logo.png 页脚 LOGO）到报告 static 目录"""
        import shutil
        brand_dir = os.path.join(settings.BASE_DIR, 'testcases', 'appuitest')
        img_dir = html_dir / 'static' / 'image'
        img_dir.mkdir(parents=True, exist_ok=True)

        # 背景水印图: JT.jpg
        jt_bg_src = os.path.join(brand_dir, 'JT.jpg')
        if os.path.isfile(jt_bg_src):
            shutil.copy2(jt_bg_src, img_dir / 'JT.jpg')

        # 页脚 LOGO: J&Tlogo.png -> company_logo.png
        logo_src = os.path.join(brand_dir, 'J&Tlogo.png')
        if os.path.isfile(logo_src):
            shutil.copy2(logo_src, img_dir / 'company_logo.png')

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

    def _generate_screenshot(self, html_path):
        """使用 Playwright 将报告 HTML 转为截图，并压缩到 18KB 以下"""
        screenshot_path = html_path.with_suffix('.jpg')
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={'width': 800, 'height': 600})
                page.goto(f'file://{html_path}')
                page.screenshot(path=str(screenshot_path), full_page=True)
                browser.close()

            self._compress_screenshot(screenshot_path)
            logger.info(f"报告截图已生成: {screenshot_path}")
        except Exception as e:
            logger.warning(f"生成报告截图失败: {e}")

    def _compress_screenshot(self, image_path, max_size=18 * 1024):
        """将图片压缩到 max_size 字节以下"""
        from PIL import Image

        img = Image.open(image_path)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        for scale in [1.0, 0.75, 0.5, 0.35, 0.25]:
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            resized = img.resize((new_w, new_h), Image.LANCZOS)
            for quality in [85, 70, 55, 40, 25]:
                resized.save(str(image_path), 'JPEG', quality=quality)
                if os.path.getsize(image_path) <= max_size:
                    return

        # 兜底：缩到 20% 并用最低质量
        img.resize(
            (int(img.width * 0.2), int(img.height * 0.2)), Image.LANCZOS
        ).save(str(image_path), 'JPEG', quality=20)

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
