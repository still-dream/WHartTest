"""
浏览器安装检查模块

用于检查 Playwright 浏览器是否已安装，若未安装则自动安装。
支持打包成 exe 后独立运行。
支持实时进度条显示和 GUI 回调。
"""

import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger('actuator.browser')


def get_exe_dir() -> Path:
    """获取 exe 所在目录或脚本所在目录"""
    if getattr(sys, 'frozen', False):
        # 打包后的 exe
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path(__file__).parent


def get_browser_path() -> Path:
    """获取浏览器存储路径（相对于 exe 目录）"""
    return get_exe_dir() / "browsers"


def setup_playwright_env() -> None:
    """设置 Playwright 环境变量，使其使用相对路径存储浏览器"""
    browser_path = get_browser_path()
    # 设置 Playwright 浏览器存储路径
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browser_path)
    logger.info(f"Playwright 浏览器路径: {browser_path}")


def is_browser_installed(browser_type: str = 'chromium') -> bool:
    """检查浏览器是否已安装"""
    browser_path = get_browser_path()
    if not browser_path.exists():
        return False

    # 检查是否有浏览器目录
    browser_dirs = list(browser_path.glob(f'{browser_type}-*'))
    return len(browser_dirs) > 0


class ProgressPrinter:
    """
    控制台进度条打印机

    特性：
    - 使用 \\r 在同一行刷新进度条
    - **不在中途向 logger 重复记录进度**（避免和进度条显示重复）
    - 仅在 finish() / error() 时记录一次总结日志
    - 线程安全
    - 兼容 Windows / Linux / macOS 控制台
    """

    BAR_WIDTH = 30

    def __init__(self, description: str = "进度", logger_instance: logging.Logger | None = None):
        self.description = description
        self.logger = logger_instance
        self._percent = 0
        self._lock = threading.Lock()
        self._newline_pending = False

    def update(self, percent: int, message: str = '') -> None:
        """更新进度（0-100），只刷新控制台进度条，不再向 logger 重复输出"""
        percent = max(0, min(100, int(percent)))

        with self._lock:
            self._percent = percent
            self._draw(message)

    def _draw(self, message: str) -> None:
        """在控制台绘制进度条（使用 \\r 原地刷新）"""
        if not sys.stdout:
            return
        filled = int(self.BAR_WIDTH * self._percent / 100)
        bar = '\u2588' * filled + '\u2591' * (self.BAR_WIDTH - filled)
        # 控制消息长度，避免进度条过长
        msg = (message or '').strip()
        if len(msg) > 40:
            msg = msg[:37] + '...'
        line = f"\r  {self.description}: [{bar}] {self._percent:3d}% {msg}"
        try:
            sys.stdout.write(line)
            sys.stdout.flush()
        except Exception:
            # 在某些受限环境下（重定向、IDE 内置终端）写入可能失败
            pass

    def newline(self) -> None:
        """结束当前进度行（打印换行），下次更新从头开始"""
        if not sys.stdout:
            return
        try:
            sys.stdout.write('\n')
            sys.stdout.flush()
        except Exception:
            pass

    def finish(self, message: str = "完成") -> None:
        """完成进度：刷到 100%、换行、记录一次总结日志"""
        self.update(100, message)
        self.newline()
        if self.logger:
            self.logger.info(f"{self.description}: {message}")

    def error(self, message: str) -> None:
        """错误状态：换行并记录错误日志"""
        self.newline()
        if self.logger:
            self.logger.error(message)


def _build_install_command(browser_type: str) -> list[str]:
    """构造 playwright install 命令"""
    if getattr(sys, 'frozen', False):
        # 打包环境：使用内置的 playwright driver
        import playwright._impl._driver as driver
        driver_executable = driver.compute_driver_executable()
        # driver_executable 是一个元组: (node.exe, cli.js)
        if isinstance(driver_executable, tuple):
            return list(driver_executable) + ['install', browser_type]
        return [str(driver_executable), 'install', browser_type]
    # 开发环境
    return [sys.executable, '-m', 'playwright', 'install', browser_type]


def install_browser(browser_type: str = 'chromium',
                    progress_callback=None) -> bool:
    """
    安装 Playwright 浏览器（带实时进度条）

    Args:
        browser_type: 浏览器类型（chromium / firefox / webkit）
        progress_callback: 可选的进度回调函数，
                          签名 progress_callback(percent: int, message: str)
                          可用于在 GUI 中显示进度

    Returns:
        True 安装成功 / False 安装失败
    """
    browser_path = get_browser_path()
    browser_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"正在安装 {browser_type} 浏览器 -> {browser_path}（首次安装可能需要几分钟）")

    printer = ProgressPrinter("浏览器安装", logger)

    try:
        # 设置环境变量
        env = os.environ.copy()
        env['PLAYWRIGHT_BROWSERS_PATH'] = str(browser_path)
        # 禁用 playwright 子进程输出 ANSI 颜色
        env['NO_COLOR'] = '1'
        env['FORCE_COLOR'] = '0'

        cmd = _build_install_command(browser_type)
        logger.info(f"执行命令: {' '.join(str(c) for c in cmd)}")

        # 启动子进程（流式输出，合并 stderr 到 stdout）
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # 行缓冲
            encoding='utf-8',
            errors='replace',
        )

        if process.stdout is None:
            logger.error("无法读取子进程输出")
            return False

        # ------------------------------------------------------------------
        # 正则集合
        # ------------------------------------------------------------------
        # 匹配 playwright 进度条："|████░░| 30%" 或 "|████░░| 30% - 15.2MB"
        progress_pattern = re.compile(r'\|\s*(\d{1,3})\s*%')
        # 备用：形如 "30% 15.2MB" 或 "30% (15.2MB/172.8MB)"
        download_pattern = re.compile(r'(\d{1,3})\s*%\s*([\d.]+\s*[KMGT]?B)')
        # 匹配下载头部：Downloading Chrome for Testing 145.0.7632.6 ...
        # 或 Downloading Chromium 130.xxxx ...
        header_pattern = re.compile(
            r'Downloading\s+(Chrome(?:\s+for\s+Testing)?|Chromium|Firefox|WebKit)\s+([\w.\-\(\)\s]+?)\s+from',
            re.IGNORECASE,
        )
        # 匹配 Node.js deprecation 警告噪声
        # 例：(node:2912) [DEP0169] DeprecationWarning: ...
        #     (Use `node --trace-deprecation ...` to show where the warning was created)
        deprecation_pattern = re.compile(
            r'\(node:\d+\)\s*\[DEP\d+\]\s*DeprecationWarning|'
            r'\(Use\s+`node\s+--trace-deprecation[^`]*`\s+to\s+show\s+where\s+the\s+warning\s+was\s+created\)',
            re.IGNORECASE,
        )

        def _emit(percent: int, message: str) -> None:
            """统一输出：进度条 + GUI 回调"""
            printer.update(percent, message)
            if progress_callback:
                try:
                    progress_callback(percent, message)
                except Exception as e:
                    logger.debug(f"进度回调异常: {e}")

        shown_header = False
        last_known_percent = 0

        try:
            for raw_line in iter(process.stdout.readline, ''):
                if not raw_line:
                    break
                line = raw_line.rstrip()
                if not line:
                    continue

                # 1) 过滤 Node.js deprecation 警告噪声
                if deprecation_pattern.search(line):
                    continue

                # 2) 匹配 playwright 进度条（|███░░| 30% ...）
                match = progress_pattern.search(line)
                if match:
                    percent = int(match.group(1))
                    extra = line[match.end():].strip()
                    last_known_percent = percent
                    _emit(percent, extra)
                    continue

                # 3) 备用：匹配 "30% 15.2MB" 这种无 bar 的格式
                dl_match = download_pattern.search(line)
                if dl_match:
                    percent = int(dl_match.group(1))
                    extra = dl_match.group(2).strip()
                    last_known_percent = percent
                    _emit(percent, extra)
                    continue

                # 4) 匹配下载头部：Downloading Chrome for Testing 145.xxxx ...
                header_match = header_pattern.search(line)
                if header_match:
                    if not shown_header:
                        # 截断 URL：只保留 "Downloading Chrome for Testing 145.0.7632.6 (...)"
                        logger.info(f"[playwright] {line}")
                        shown_header = True
                    _emit(0, "下载中...")
                    continue

                # 5) 其它非进度行：结束进度行 + 降级到 DEBUG 记录
                if last_known_percent > 0 or printer._percent > 0:
                    printer.newline()
                    last_known_percent = 0
                # 重要信息（如 "Chrome downloaded to ..."）保留为 INFO
                # 但要先去掉行尾可能的 URL 长字符串
                compact = re.sub(r'\s+', ' ', line).strip()
                if any(kw in compact.lower() for kw in ('downloaded to', 'extracted to', 'installed at')):
                    logger.info(f"[playwright] {compact}")
                else:
                    logger.debug(f"[playwright] {compact}")

        except (KeyboardInterrupt, SystemExit):
            logger.warning("用户中断安装，正在终止 playwright 进程...")
            try:
                process.terminate()
            except Exception:
                pass
            return False
        except Exception as e:
            logger.error(f"读取安装输出失败: {e}")
        finally:
            try:
                process.stdout.close()  # type: ignore[union-attr]
            except Exception:
                pass

        # 等待进程结束
        try:
            return_code = process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logger.error("等待 playwright 进程结束超时，强制终止")
            try:
                process.kill()
            except Exception:
                pass
            return_code = -1

        if return_code == 0:
            printer.finish(f"安装成功 ({browser_type})")
            if progress_callback:
                try:
                    progress_callback(100, "安装完成")
                except Exception:
                    pass
            return True
        else:
            printer.error(f"浏览器安装失败，返回码: {return_code}")
            return False

    except subprocess.TimeoutExpired:
        printer.error("浏览器安装超时（>10分钟）")
        return False
    except FileNotFoundError as e:
        printer.error(f"找不到可执行文件: {e}")
        return False
    except Exception as e:
        printer.error(f"浏览器安装异常: {e}")
        return False


def ensure_browser(browser_type: str = 'chromium',
                   progress_callback=None) -> bool:
    """
    确保浏览器已安装，未安装则自动安装

    Args:
        browser_type: 浏览器类型
        progress_callback: 进度回调函数
    """
    setup_playwright_env()

    if is_browser_installed(browser_type):
        logger.info(f"{browser_type} 浏览器已安装")
        return True

    logger.info(f"未检测到 {browser_type} 浏览器，开始安装...")
    return install_browser(browser_type, progress_callback=progress_callback)


if __name__ == '__main__':
    # 测试
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )
    ensure_browser('chromium')
