"""
Playwright 脚本生成器

从 Agent 执行的 Playwright MCP 操作步骤生成可重复执行的 Python 脚本
"""
from __future__ import annotations

import json
import re
import logging
from typing import Optional, TYPE_CHECKING
from datetime import datetime

from django.utils import timezone

from .slider_captcha import get_inline_slider_code

if TYPE_CHECKING:
    from .models import AutomationScript

logger = logging.getLogger(__name__)


def convert_js_to_python_playwright(js_code: str) -> Optional[str]:
    """
    将 Playwright JS 代码转换为 Python 代码
    
    示例:
    输入: await page.getByRole('textbox', { name: '请输入用户名' }).fill('admin');
    输出: page.get_by_role('textbox', name='请输入用户名').fill('admin')
    """
    if not js_code or not isinstance(js_code, str):
        return None
    
    code = js_code.strip()
    
    # 移除 await 前缀和末尾分号
    code = re.sub(r'^await\s+', '', code)
    code = re.sub(r';$', '', code)
    
    # 转换方法名：getByRole -> get_by_role, getByText -> get_by_text, etc.
    replacements = [
        ('getByRole', 'get_by_role'),
        ('getByText', 'get_by_text'),
        ('getByLabel', 'get_by_label'),
        ('getByPlaceholder', 'get_by_placeholder'),
        ('getByAltText', 'get_by_alt_text'),
        ('getByTitle', 'get_by_title'),
        ('getByTestId', 'get_by_test_id'),
        ('locator', 'locator'),
        ('waitForTimeout', 'wait_for_timeout'),
        ('waitForSelector', 'wait_for_selector'),
        ('waitForLoadState', 'wait_for_load_state'),
        ('selectOption', 'select_option'),
    ]
    for js_name, py_name in replacements:
        code = code.replace(js_name, py_name)
    
    # 转换 JS 对象字面量为 Python 关键字参数
    # { name: '...' } -> name='...'
    # { name: '...', exact: true } -> name='...', exact=True
    def convert_js_object(match):
        obj_content = match.group(1)
        # 解析简单的 JS 对象
        pairs = []
        # 匹配 key: value 模式
        for pair_match in re.finditer(r"(\w+):\s*('[^']*'|\"[^\"]*\"|true|false|\d+)", obj_content):
            key = pair_match.group(1)
            value = pair_match.group(2)
            # 转换布尔值
            if value == 'true':
                value = 'True'
            elif value == 'false':
                value = 'False'
            pairs.append(f"{key}={value}")
        return ', ' + ', '.join(pairs) if pairs else ''
    
    # 匹配 get_by_role('...', { ... })
    code = re.sub(r",\s*\{\s*([^}]+)\s*\}", convert_js_object, code)
    
    return code
# MCP 工具名到 Playwright 代码的映射
TOOL_MAPPING = {
    'browser_navigate': 'page.goto("{url}")',
    'mcp_chrome-devtoo_navigate': 'page.goto("{url}")',
    'browser_click': 'page.locator("{selector}").click()',
    'mcp_chrome-devtoo_click': 'page.locator("[data-uid=\\"{uid}\\"]").click()',
    'browser_fill': 'page.locator("{selector}").fill("{value}")',
    'mcp_chrome-devtoo_fill': 'page.locator("[data-uid=\\"{uid}\\"]").fill("{value}")',
    'browser_type': 'page.locator("{selector}").type("{text}")',
    'mcp_chrome-devtoo_type': 'page.locator("[data-uid=\\"{uid}\\"]").type("{text}")',
    'browser_select': 'page.locator("{selector}").select_option("{value}")',
    'browser_hover': 'page.locator("{selector}").hover()',
    'mcp_chrome-devtoo_hover': 'page.locator("[data-uid=\\"{uid}\\"]").hover()',
    'browser_screenshot': 'page.screenshot(path="{path}")',
    'mcp_chrome-devtoo_screenshot': 'page.screenshot(path="{path}")',
    'browser_wait': 'page.wait_for_timeout({timeout})',
    'mcp_chrome-devtoo_wait_for': 'page.wait_for_selector("{selector}")',
    'browser_press': 'page.keyboard.press("{key}")',
    'mcp_chrome-devtoo_press_key': 'page.keyboard.press("{key}")',
}

# Playwright 脚本模板（pytest 版本）
SCRIPT_TEMPLATE = '''"""
自动化测试脚本
生成时间: {generated_at}
测试用例: {test_case_name}
目标URL: {target_url}
"""
import pytest
from playwright.sync_api import Page, expect


{slider_captcha_code}


class Test{class_name}:
    """
    {test_case_name} 自动化测试
    """
    
    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """测试前置设置"""
        self.page = page
        # 设置默认超时
        page.set_default_timeout({timeout} * 1000)
    
    def test_{method_name}(self, page: Page):
        """
        {test_description}
        """
{test_steps}
'''

# 简化模板（无 pytest，支持录屏 + 滑块验证 + 截图保存）
SIMPLE_SCRIPT_TEMPLATE = '''"""
自动化测试脚本
生成时间: {generated_at}
测试用例: {test_case_name}
目标URL: {target_url}
"""
import os
from playwright.sync_api import sync_playwright


{slider_captcha_code}


# ======================= 截图保存 =======================
# 优先使用 SKILL 传入的 SCREENSHOT_DIR，其次使用全局配置的 PLAYWRIGHT_SCREENSHOT_DIR，最后使用默认目录
SCREENSHOT_DIR = os.environ.get(
    'SCREENSHOT_DIR', 
    os.environ.get('PLAYWRIGHT_SCREENSHOT_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'playwright-screenshots'))
)


def _take_screenshot(page, filename):
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        page.screenshot(path=filepath)
        print(f"Screenshot saved: {{filepath}}")
        return filepath
    except Exception as e:
        print(f"Screenshot failed: {{e}}")
        return None


# ======================= 主流程 =======================
def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless={headless})
        
        # 录屏配置
        video_dir = os.environ.get('PLAYWRIGHT_VIDEO_DIR', '')
        context_options = {{"ignore_https_errors": True}}
        if video_dir:
            context_options["record_video_dir"] = video_dir
            context_options["record_video_size"] = {{"width": 1280, "height": 720}}
        
        context = browser.new_context(**context_options)
        page = context.new_page()
        page.set_default_timeout({timeout} * 1000)
        
        try:
{test_steps}
            print("测试执行成功")
        except Exception as e:
            print(f"测试执行失败: {{e}}")
            _take_screenshot(page, "error_screenshot.png")
            raise
        finally:
            # 关闭上下文以确保视频保存完成
            context.close()
            browser.close()


if __name__ == "__main__":
    run()
'''


class PlaywrightScriptGenerator:
    """
    将 Agent 记录的 MCP 操作步骤转换为 Playwright Python 脚本
    """
    
    def __init__(self, use_pytest: bool = True):
        self.use_pytest = use_pytest
    
    def generate_script(
        self,
        recorded_steps: list,
        test_case_name: str,
        target_url: str = '',
        timeout_seconds: int = 100,
        headless: bool = True,
        description: str = ''
    ) -> str:
        """
        生成 Playwright 脚本
        
        Args:
            recorded_steps: 记录的操作步骤列表
            test_case_name: 测试用例名称
            target_url: 目标URL
            timeout_seconds: 超时时间
            headless: 是否无头模式
            description: 测试描述
        
        Returns:
            生成的 Python 脚本字符串
        """
        steps_code = self._generate_steps_code(recorded_steps)
        
        # 清理类名和方法名
        class_name = self._sanitize_name(test_case_name, capitalize=True)
        method_name = self._sanitize_name(test_case_name, capitalize=False)
        
        if self.use_pytest:
            indent = '        '  # pytest 方法内的缩进
            steps_with_slider = self._inject_slider_captcha_step(steps_code, indent)
            formatted_steps = '\n'.join(f'{indent}{line}' for line in steps_with_slider if line.strip())
            formatted_steps_escaped = formatted_steps.replace('{', '{{').replace('}', '}}')
            slider_captcha_code = get_inline_slider_code().strip()
            slider_captcha_code_escaped = slider_captcha_code.replace('{', '{{').replace('}', '}}')
            
            return SCRIPT_TEMPLATE.format(
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                test_case_name=test_case_name,
                target_url=target_url or '未指定',
                class_name=class_name,
                method_name=method_name,
                timeout=timeout_seconds,
                test_description=description or test_case_name,
                test_steps=formatted_steps_escaped,
                slider_captcha_code=slider_captcha_code_escaped
            )
        else:
            indent = '            '  # 简单模板的缩进
            steps_with_slider = self._inject_slider_captcha_step(steps_code, indent)
            formatted_steps = '\n'.join(f'{indent}{line}' for line in steps_with_slider if line.strip())
            formatted_steps_escaped = formatted_steps.replace('{', '{{').replace('}', '}}')
            slider_captcha_code = get_inline_slider_code().strip()
            slider_captcha_code_escaped = slider_captcha_code.replace('{', '{{').replace('}', '}}')
            
            return SIMPLE_SCRIPT_TEMPLATE.format(
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                test_case_name=test_case_name,
                target_url=target_url or '未指定',
                timeout=timeout_seconds,
                headless=str(headless),
                test_steps=formatted_steps_escaped,
                slider_captcha_code=slider_captcha_code_escaped
            )
    
    def _generate_steps_code(self, recorded_steps: list) -> list[str]:
        """
        将记录的步骤转换为代码行
        """
        code_lines = []
        
        for i, step in enumerate(recorded_steps, 1):
            tool_name = step.get('tool_name', '')
            tool_input = step.get('tool_input', {})
            
            # 添加步骤注释 - 清理为单行并移除特殊字符
            step_comment = step.get('description', f'步骤 {i}')
            step_comment = self._sanitize_comment(step_comment)
            code_lines.append(f'# {step_comment}')
            
            # 生成代码
            code_line = self._generate_step_code(tool_name, tool_input)
            if code_line:
                code_lines.append(code_line)
            else:
                code_lines.append(f'# 未知操作: {tool_name}')
            
            code_lines.append('')  # 空行分隔
        
        return code_lines

    def _inject_slider_captcha_step(self, code_lines: list[str], indent: str) -> list[str]:
        """
        在登录流程（点击登录按钮）后自动注入滑块验证码检测和处理步骤

        检测逻辑：遍历生成的代码行，当发现包含登录按钮点击操作
        （如 click、login 等关键词）时，在其后插入 _handle_slider_captcha(page) 调用。

        Args:
            code_lines: 原始步骤代码行列表
            indent: 代码缩进字符串

        Returns:
            注入滑块验证码步骤后的代码行列表
        """
        login_click_patterns = [
            r'\.click\(\)',
            r'login',
            r'登录',
            r'sign.?in',
            r'submit',
        ]
        login_indicator_patterns = [
            r'login',
            r'登录',
            r'sign.?in',
            r'btn.*login',
            r'button.*login',
        ]
        result = []
        injected = False

        for i, line in enumerate(code_lines):
            result.append(line)

            if injected:
                continue

            is_click_action = '.click()' in line
            if not is_click_action:
                continue

            line_lower = line.lower()
            comment_line = ''
            for j in range(i - 1, -1, -1):
                stripped = code_lines[j].strip()
                if stripped.startswith('#'):
                    comment_line = stripped.lower()
                    break
                elif stripped:
                    break

            is_login_related = False
            for pattern in login_indicator_patterns:
                if re.search(pattern, line_lower) or re.search(pattern, comment_line):
                    is_login_related = True
                    break

            if not is_login_related:
                for j in range(max(0, i - 5), i):
                    nearby = code_lines[j].lower()
                    for pattern in login_indicator_patterns:
                        if re.search(pattern, nearby):
                            is_login_related = True
                            break
                    if is_login_related:
                        break

            if is_login_related:
                result.append('')
                result.append('# 检测并处理滑块验证码')
                result.append('slider_result = _handle_slider_captcha(page, max_retries=20)')
                result.append('if not slider_result:')
                result.append(f'    print("滑块验证失败，脚本终止")')
                result.append(f'    return')
                injected = True

        if not injected:
            result.append('')
            result.append('# 检测并处理滑块验证码（如有）')
            result.append('_handle_slider_captcha(page, max_retries=20)')

        return result

    def _sanitize_comment(self, comment: str) -> str:
        """
        清理注释文本，确保是有效的 Python 单行注释
        - 替换换行符为空格
        - 限制长度
        - 移除不安全的字符
        """
        if not comment:
            return ''
        # 替换换行符为空格
        sanitized = comment.replace('\n', ' ').replace('\r', ' ')
        # 移除多余空格
        sanitized = ' '.join(sanitized.split())
        # 限制长度
        if len(sanitized) > 80:
            sanitized = sanitized[:77] + '...'
        return sanitized
    
    def _generate_step_code(self, tool_name: str, tool_input: dict) -> Optional[str]:
        """
        根据工具名和输入生成单行代码
        """
        template = TOOL_MAPPING.get(tool_name)
        if not template:
            return None
        
        try:
            # 处理不同工具的参数
            params = self._extract_params(tool_name, tool_input)
            return template.format(**params)
        except KeyError as e:
            logger.warning(f"生成脚本时缺少参数: {e}, tool={tool_name}, input={tool_input}")
            return f'# 参数缺失: {tool_name}'
    
    def _extract_params(self, tool_name: str, tool_input: dict) -> dict:
        """
        从工具输入中提取模板所需的参数
        """
        params = {}
        
        # 统一处理 URL
        if 'url' in tool_input:
            params['url'] = tool_input['url']
        
        # 处理选择器
        if 'selector' in tool_input:
            params['selector'] = self._escape_string(tool_input['selector'])
        elif 'uid' in tool_input:
            params['uid'] = tool_input['uid']
        elif 'element' in tool_input:
            params['selector'] = self._escape_string(tool_input['element'])
        
        # 处理值
        if 'value' in tool_input:
            params['value'] = self._escape_string(tool_input['value'])
        if 'text' in tool_input:
            params['text'] = self._escape_string(tool_input['text'])
        
        # 处理按键
        if 'key' in tool_input:
            params['key'] = tool_input['key']
        
        # 处理超时
        if 'timeout' in tool_input:
            params['timeout'] = tool_input['timeout']
        
        # 处理截图路径
        if 'path' in tool_input:
            params['path'] = tool_input['path']
        elif tool_name in ['browser_screenshot', 'mcp_chrome-devtoo_screenshot']:
            params['path'] = f'screenshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        
        return params
    
    def _escape_string(self, s: str) -> str:
        """
        安全转义字符串，用于嵌入 Python 代码
        使用 repr() 确保所有特殊字符都被正确转义
        """
        if not isinstance(s, str):
            s = str(s)
        # 使用 repr() 生成安全的 Python 字符串表示
        # 然后去掉外层引号，因为模板中已有引号
        escaped = repr(s)
        # repr 返回 'string' 或 "string"，去掉外层引号
        if escaped.startswith("'") and escaped.endswith("'"):
            return escaped[1:-1].replace('"', '\\"')
        elif escaped.startswith('"') and escaped.endswith('"'):
            return escaped[1:-1]
        return escaped
    
    def _sanitize_name(self, name: str, capitalize: bool = False) -> str:
        """
        清理名称，使其成为有效的 Python 标识符
        """
        import re
        
        # 移除非字母数字字符
        sanitized = re.sub(r'[^\w\s]', '', name)
        # 用下划线替换空格
        sanitized = re.sub(r'\s+', '_', sanitized)
        # 确保不以数字开头
        if sanitized and sanitized[0].isdigit():
            sanitized = '_' + sanitized
        
        if capitalize:
            # 转为 PascalCase
            return ''.join(word.capitalize() for word in sanitized.split('_'))
        else:
            # 转为 snake_case
            return sanitized.lower()
