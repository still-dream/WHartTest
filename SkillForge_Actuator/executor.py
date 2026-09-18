"""
UI自动化执行器 - Python Playwright执行引擎
使用Python原生Playwright库执行测试，无需Node.js依赖
"""

import asyncio
import logging
import time
import traceback
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright, expect

from models import StepResultModel, CaseResultModel

logger = logging.getLogger('actuator')


@dataclass
class StepConfig:
    """步骤配置"""
    step_id: int
    operation_type: str      # click, fill, goto, wait, assert等
    locator_type: str        # xpath, css, id等
    locator_value: str
    locator_index: int = 0   # 元素下标(0=不取nth, 1=nth(1)...)
    # 备用定位 1(主定位失败时回退)
    locator_type_2: str = ''
    locator_value_2: str = ''
    locator_index_2: int = 0
    # 备用定位 2(备用1失败时再回退)
    locator_type_3: str = ''
    locator_value_3: str = ''
    locator_index_3: int = 0
    input_value: str = ''
    description: str = ''
    wait_time: float = 0

    # 步骤详情(公共步骤)
    details: list['StepConfig'] = field(default_factory=list)


@dataclass 
class PageStepConfig:
    """页面步骤配置"""
    page_step_id: int
    page_url: str
    page_name: str
    steps: list[StepConfig] = field(default_factory=list)


@dataclass
class TestCaseConfig:
    """测试用例配置"""
    case_id: int
    case_name: str
    page_steps: list[PageStepConfig] = field(default_factory=list)
    env_config: Optional[dict] = None


class PlaywrightExecutor:
    """Python原生Playwright执行器"""
    
    def __init__(
        self, 
        browser_type: str = 'chromium',
        headless: bool = False,
        persistent: bool = True,
        user_data_dir: str = './data/browser',
        launch_timeout: int = 30000,
        action_timeout: int = 30000,
        screenshot_dir: str = './data/screenshots',
        trace_enabled: bool = False,
        trace_dir: str = './data/traces',
        trace_screenshots: bool = True,
        trace_snapshots: bool = True,
        trace_sources: bool = False,
        # 元素操作失败后的重试次数(0 = 不重试)
        retry_count: int = 0,
        # 步骤间隔(毫秒), 每步操作成功后等待
        step_interval: int = 0,
        # 用例结束后浏览器额外等待(毫秒), 用于 trace 补抓最后帧
        tail_wait_ms: int = 1000,
    ):
        self.browser_type = browser_type
        self.headless = headless
        self.persistent = persistent
        self.user_data_dir = user_data_dir
        self.launch_timeout = launch_timeout
        self.action_timeout = action_timeout
        self.screenshot_dir = screenshot_dir
        
        # Trace 配置
        self.trace_enabled = trace_enabled
        self.trace_dir = trace_dir
        self.trace_screenshots = trace_screenshots
        self.trace_snapshots = trace_snapshots
        self.trace_sources = trace_sources
        # 执行配置
        self.retry_count = retry_count
        self.step_interval = step_interval
        self.tail_wait_ms = tail_wait_ms
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._stop_requested = False
        self._current_trace_path: Optional[str] = None
        
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.screenshot_dir).mkdir(parents=True, exist_ok=True)
        if self.trace_enabled:
            Path(self.trace_dir).mkdir(parents=True, exist_ok=True)
    
    async def init_browser(self) -> None:
        """初始化浏览器"""
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        
        browser_launcher = getattr(self._playwright, self.browser_type)
        
        if self.persistent:
            self._context = await browser_launcher.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                timeout=self.launch_timeout,
            )
            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()
        else:
            self._browser = await browser_launcher.launch(
                headless=self.headless,
                timeout=self.launch_timeout,
            )
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
        
        self._page.set_default_timeout(self.action_timeout)
        logger.info(f"浏览器已初始化: {self.browser_type}, headless={self.headless}")
    
    async def close(self) -> None:
        """关闭浏览器"""
        if self._context:
            await self._context.close()
            self._context = None
            self._page = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("浏览器已关闭")
    
    @asynccontextmanager
    async def browser_session(self):
        """浏览器会话上下文管理器"""
        await self.init_browser()
        try:
            yield self._page
        finally:
            await self.close()
    
    @asynccontextmanager
    async def browser_session_with_trace(self, trace_name: str = 'trace'):
        """带 Trace 的浏览器会话上下文管理器
        
        Args:
            trace_name: trace 文件名前缀（不含扩展名）
            
        Yields:
            Page: 页面对象
            
        Returns:
            trace 文件路径（通过 self._current_trace_path 获取）
        """
        await self.init_browser()
        self._current_trace_path = None
        
        try:
            # 启动 Trace
            if self.trace_enabled and self._context:
                await self._context.tracing.start(
                    screenshots=self.trace_screenshots,
                    snapshots=self.trace_snapshots,
                    sources=self.trace_sources,
                )
                logger.debug(f"Trace 已启动: screenshots={self.trace_screenshots}, snapshots={self.trace_snapshots}")
            
            yield self._page
            
        finally:
            # 停止 Trace 并保存
            # 停止前等 1 秒, 让 trace 多抓最后一帧截图(避免最后 1-2 秒画面缺失)
            if self.trace_enabled and self._context:
                try:
                    if self._page and not self._page.is_closed():
                        logger.debug(f"Trace 停止前等待 {self.tail_wait_ms}ms, 以抓取最后帧")
                        await self._page.wait_for_timeout(self.tail_wait_ms)
                except Exception as e:
                    logger.warning(f"Trace 尾部等待失败(忽略): {e}")

                try:
                    timestamp = int(time.time() * 1000)
                    trace_path = f"{self.trace_dir}/{trace_name}_{timestamp}.zip"
                    await self._context.tracing.stop(path=trace_path)
                    self._current_trace_path = trace_path
                    logger.info(f"Trace 已保存: {trace_path}")
                except Exception as e:
                    logger.error(f"保存 Trace 失败: {e}")

            await self.close()
    
    def get_current_trace_path(self) -> Optional[str]:
        """获取当前执行的 trace 文件路径"""
        return self._current_trace_path

    def stop(self):
        """请求停止执行"""
        self._stop_requested = True
    
    def _get_locator(self, page: Page, locator_type: str, locator_value: str, locator_index: int = 0):
        """根据定位类型获取元素定位器
        
        Args:
            page: Playwright Page 对象
            locator_type: 定位类型 (xpath/css/id/name/text/role/placeholder/label/testid)
            locator_value: 定位表达式
            locator_index: 元素下标, 0=不取 nth(默认第一个匹配); >0 时调用 .nth(n)
        """
        locator_map = {
            'xpath': lambda: page.locator(f"xpath={locator_value}"),
            'css': lambda: page.locator(locator_value),
            'id': lambda: page.locator(f"#{locator_value}"),
            'name': lambda: page.locator(f"[name='{locator_value}']"),
            'text': lambda: page.get_by_text(locator_value),
            'role': lambda: page.get_by_role(locator_value),
            'placeholder': lambda: page.get_by_placeholder(locator_value),
            'label': lambda: page.get_by_label(locator_value),
            'testid': lambda: page.get_by_test_id(locator_value),
        }
        loc = locator_map.get(locator_type, lambda: page.locator(locator_value))()
        # 当 index > 0 时,取第 index 个匹配元素
        if locator_index and locator_index > 0:
            loc = loc.nth(locator_index)
        return loc

    def _build_locator_chain(self, page: Page, step: StepConfig) -> list[tuple[str, object]]:
        """构建定位器回退链: [(描述, locator), ...]
        
        按 主定位 → 备用1 → 备用2 的顺序构造。
        备用定位只有在 type 和 value 都不为空时才会加入链。
        """
        chain: list[tuple[str, object]] = []

        if step.locator_value and step.locator_value.strip():
            chain.append((
                f"主定位[{step.locator_type}={step.locator_value}, index={step.locator_index}]",
                self._get_locator(page, step.locator_type, step.locator_value, step.locator_index)
            ))

        if step.locator_type_2 and step.locator_value_2 and step.locator_value_2.strip():
            chain.append((
                f"备用1[{step.locator_type_2}={step.locator_value_2}, index={step.locator_index_2}]",
                self._get_locator(page, step.locator_type_2, step.locator_value_2, step.locator_index_2 or 0)
            ))

        if step.locator_type_3 and step.locator_value_3 and step.locator_value_3.strip():
            chain.append((
                f"备用2[{step.locator_type_3}={step.locator_value_3}, index={step.locator_index_3}]",
                self._get_locator(page, step.locator_type_3, step.locator_value_3, step.locator_index_3 or 0)
            ))

        return chain
    
    async def _execute_step(self, page: Page, step: StepConfig) -> tuple[bool, str, str | None]:
        """执行单个步骤
        
        Returns:
            tuple: (成功与否, 消息, 截图路径(可选))
        """
        operation = step.operation_type.lower()
        screenshot_path: str | None = None
        
        # 等待时间（仅当用户明确设置 > 0 时才等待，用于特殊场景）
        # 注意：Playwright 自带 Auto-waiting，一般不需要手动等待
        if step.wait_time > 0:
            logger.debug(f"步骤 {step.step_id}: 强制等待 {step.wait_time}s（建议设为0让Playwright自动等待）")
            await page.wait_for_timeout(int(step.wait_time * 1000))
        
        # 记录开始时间
        op_start = time.time()
        
        # screenshot 操作特殊处理，保存路径
        if operation == 'screenshot':
            screenshot_path = step.input_value or f"{self.screenshot_dir}/step_{step.step_id}.png"
            await page.screenshot(path=screenshot_path)
            logger.debug(f"步骤 {step.step_id}: screenshot 耗时 {time.time() - op_start:.2f}s")
            return True, f"页面操作 {operation} 执行成功", screenshot_path
        
        # 页面操作（不需要定位器）
        def _parse_wait_timeout(value: str) -> int:
            """解析等待时间（毫秒）"""
            if not value:
                return 1000  # 默认 1 秒
            try:
                return int(float(value))
            except ValueError:
                return 1000

        page_operations = {
            'goto': lambda: page.goto(step.input_value),
            'reload': lambda: page.reload(),
            'go_back': lambda: page.go_back(),
            'go_forward': lambda: page.go_forward(),
            'wait': lambda: page.wait_for_timeout(_parse_wait_timeout(step.input_value)),
            'wait_load': lambda: page.wait_for_load_state("load"),
            'wait_network': lambda: page.wait_for_load_state("networkidle"),
        }
        
        if operation in page_operations:
            await page_operations[operation]()
            logger.debug(f"步骤 {step.step_id}: {operation} 耗时 {time.time() - op_start:.2f}s")
            return True, f"页面操作 {operation} 执行成功", None
        
        # 元素操作（需要定位器, 支持主定位→备用1→备用2 的回退）
        if not step.locator_value or not step.locator_value.strip():
            return False, f"元素定位器为空，请在元素管理中配置定位表达式（步骤: {step.description or step.step_id}）", None

        locator_chain = self._build_locator_chain(page, step)
        if not locator_chain:
            return False, f"元素定位器为空，请在元素管理中配置定位表达式（步骤: {step.description or step.step_id}）", None

        locator_start = time.time()
        chain_desc = " → ".join(desc for desc, _ in locator_chain)
        logger.debug(f"步骤 {step.step_id}: 定位器链 [{chain_desc}] 耗时 {time.time() - locator_start:.2f}s")

        # 元素操作闭包: 给定一个 locator, 返回对应的 Playwright 异步操作
        def _click_loc(loc):    return loc.click()
        def _dblclick_loc(loc): return loc.dblclick()
        def _fill_loc(loc):     return loc.fill(step.input_value)
        def _type_loc(loc):     return loc.type(step.input_value)
        def _clear_loc(loc):    return loc.fill("")
        def _check_loc(loc):    return loc.check()
        def _uncheck_loc(loc):  return loc.uncheck()
        def _select_loc(loc):   return loc.select_option(step.input_value)
        def _hover_loc(loc):    return loc.hover()
        def _focus_loc(loc):    return loc.focus()
        def _press_loc(loc):    return loc.press(step.input_value)
        def _upload_loc(loc):   return loc.set_input_files(step.input_value)

        element_op_map = {
            'click':    _click_loc,
            'dblclick': _dblclick_loc,
            'fill':     _fill_loc,
            'type':     _type_loc,
            'clear':    _clear_loc,
            'check':    _check_loc,
            'uncheck':  _uncheck_loc,
            'select':   _select_loc,
            'hover':    _hover_loc,
            'focus':    _focus_loc,
            'press':    _press_loc,
            'upload':   _upload_loc,
        }

        if operation in element_op_map:
            action_start = time.time()
            op_fn = element_op_map[operation]
            # 元素操作层重试: 总尝试次数 = retry_count + 1
            total_attempts = max(1, self.retry_count + 1)
            last_error: Exception | None = None
            for attempt in range(1, total_attempts + 1):
                for idx, (desc, loc) in enumerate(locator_chain):
                    try:
                        await op_fn(loc)
                        action_time = time.time() - action_start
                        used = "主定位" if idx == 0 else f"备用{idx}"
                        logger.debug(f"步骤 {step.step_id}: {operation} 使用 {used} 成功 ({desc}) 第{attempt}/{total_attempts}次尝试 耗时 {action_time:.2f}s (总计 {time.time() - op_start:.2f}s)")
                        # 成功后, 等待 step_interval 毫秒(给页面渲染留缓冲)
                        if self.step_interval and self.step_interval > 0:
                            await page.wait_for_timeout(self.step_interval)
                        return True, f"元素操作 {operation} 执行成功", None
                    except Exception as e:
                        last_error = e
                        if idx + 1 < len(locator_chain):
                            logger.warning(f"步骤 {step.step_id}: {operation} 第{attempt}/{total_attempts}次: {desc} 失败: {e}, 尝试下一个定位器")
                # 一轮回退链都失败, 如果还有重试次数则等 500ms 再来
                if attempt < total_attempts:
                    logger.warning(f"步骤 {step.step_id}: {operation} 第{attempt}轮所有定位器失败, 500ms 后重试")
                    await page.wait_for_timeout(500)
            logger.error(f"步骤 {step.step_id}: {operation} 重试{self.retry_count}次后仍失败, 最后错误: {last_error}")
            return False, f"元素操作 {operation} 失败(重试{self.retry_count}次): {last_error}", None

        # 断言操作(同样走回退链)
        if operation.startswith('assert_'):
            assert_type = operation.replace('assert_', '')
            assert_op_map = {
                'visible':       lambda loc: expect(loc).to_be_visible(),
                'hidden':        lambda loc: expect(loc).to_be_hidden(),
                'enabled':       lambda loc: expect(loc).to_be_enabled(),
                'disabled':      lambda loc: expect(loc).to_be_disabled(),
                'checked':       lambda loc: expect(loc).to_be_checked(),
                'text':          lambda loc: expect(loc).to_have_text(step.input_value),
                'value':         lambda loc: expect(loc).to_have_value(step.input_value),
                'contain_text':  lambda loc: expect(loc).to_contain_text(step.input_value),
            }
            # url/title 是页面级断言, 不走回退
            page_assert_map = {
                'url':   lambda: expect(page).to_have_url(step.input_value),
                'title': lambda: expect(page).to_have_title(step.input_value),
            }

            if assert_type in page_assert_map:
                await page_assert_map[assert_type]()
                logger.debug(f"步骤 {step.step_id}: assert_{assert_type} 耗时 {time.time() - op_start:.2f}s")
                return True, f"断言 {assert_type} 通过", None

            if assert_type in assert_op_map:
                assert_fn = assert_op_map[assert_type]
                last_error: Exception | None = None
                for idx, (desc, loc) in enumerate(locator_chain):
                    try:
                        await assert_fn(loc)
                        used = "主定位" if idx == 0 else f"备用{idx}"
                        logger.debug(f"步骤 {step.step_id}: assert_{assert_type} 使用 {used} 成功 ({desc}) 耗时 {time.time() - op_start:.2f}s")
                        return True, f"断言 {assert_type} 通过", None
                    except Exception as e:
                        last_error = e
                        if idx + 1 < len(locator_chain):
                            logger.warning(f"步骤 {step.step_id}: assert_{assert_type} 使用 {desc} 失败: {e}, 尝试下一个定位器")
                        else:
                            logger.error(f"步骤 {step.step_id}: assert_{assert_type} 全部定位器均失败, 最后错误: {e}")
                return False, f"断言 {assert_type} 失败: {last_error}", None

        return False, f"未知操作类型: {operation}", None
    
    async def execute_step(self, step: StepConfig, page_url: str = '') -> StepResultModel:
        """执行单个步骤（独立浏览器会话）"""
        start_time = time.time()
        
        try:
            async with self.browser_session() as page:
                if page_url:
                    await page.goto(page_url)
                
                success, message, step_screenshot = await self._execute_step(page, step)
                duration = time.time() - start_time
                
                return StepResultModel(
                    step_id=step.step_id,
                    status='success' if success else 'failed',
                    message=message,
                    description=step.description or step.operation_type,
                    duration=duration,
                    element_found=success,
                    screenshot=step_screenshot
                )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"步骤执行失败: {e}\n{traceback.format_exc()}")
            return StepResultModel(
                step_id=step.step_id,
                status='failed',
                message=str(e),
                description=step.description or step.operation_type,
                duration=duration,
                element_found=False
            )
    
    async def execute_test_case(self, config: TestCaseConfig) -> CaseResultModel:
        """执行测试用例（支持 Trace 记录）"""
        start_time = time.time()
        step_results = []
        passed_steps = 0
        failed_steps = 0
        total_steps = sum(len(ps.steps) for ps in config.page_steps)
        
        self._stop_requested = False
        trace_name = f"case_{config.case_id}"
        
        try:
            # 使用带 trace 的浏览器会话
            async with self.browser_session_with_trace(trace_name) as page:
                logger.info(f"开始执行用例: {config.case_name}")

                # 浏览器启动后，立即导航到环境配置的 base_url
                base_url = ''
                if config.env_config:
                    base_url = config.env_config.get('base_url', '') or ''
                if base_url:
                    logger.info(f"导航到环境 base_url: {base_url}")
                    await page.goto(base_url, wait_until="networkidle")

                for page_step in config.page_steps:
                    if self._stop_requested:
                        raise Exception("用例被手动停止")

                    logger.info(f"执行页面步骤: {page_step.page_name}")

                    # 检测页面跳转：仅当下一个页面 URL 与当前不同时才等待
                    if page_step.page_url:
                        current_url = page.url
                        expected_url = page_step.page_url.rstrip('/')
                        
                        # 只有当期望的 URL 与当前 URL 不同时，才等待跳转
                        if expected_url not in current_url:
                            try:
                                # 短暂等待，检测是否有 URL 变化
                                await page.wait_for_url(
                                    lambda url: url != current_url,
                                    timeout=2000
                                )
                                logger.debug(f"检测到页面跳转: {current_url} -> {page.url}")
                            except Exception:
                                # 没有页面跳转是正常情况
                                pass
                    
                    # 执行页面内的步骤
                    for step in page_step.steps:
                        if self._stop_requested:
                            raise Exception("用例被手动停止")
                        
                        step_start = time.time()
                        try:
                            success, message, step_screenshot = await self._execute_step(page, step)
                            step_duration = time.time() - step_start

                            step_result = StepResultModel(
                                step_id=step.step_id,
                                status='success' if success else 'failed',
                                message=message,
                                description=step.description or step.operation_type,
                                duration=step_duration,
                                element_found=success,
                                screenshot=step_screenshot  # 保存截图操作的路径
                            )

                            if success:
                                passed_steps += 1
                                logger.debug(f"  ✅ {step.description or step.operation_type}")
                            else:
                                failed_steps += 1
                                logger.warning(f"  ❌ {step.description or step.operation_type}: {message}")
                                # 失败时额外截图
                                if not step_screenshot:
                                    screenshot_path = f"{self.screenshot_dir}/fail_{config.case_id}_{step.step_id}.png"
                                    await page.screenshot(path=screenshot_path)
                                    step_result.screenshot = screenshot_path

                        except Exception as step_error:
                            step_duration = time.time() - step_start
                            failed_steps += 1
                            error_msg = str(step_error)
                            logger.error(f"  ❌ {step.description or step.operation_type}: {error_msg}")

                            # 失败时截图
                            try:
                                screenshot_path = f"{self.screenshot_dir}/error_{config.case_id}_{step.step_id}.png"
                                await page.screenshot(path=screenshot_path)
                            except:
                                screenshot_path = None

                            step_result = StepResultModel(
                                step_id=step.step_id,
                                status='failed',
                                message=error_msg,
                                description=step.description or step.operation_type,
                                duration=step_duration,
                                element_found=False,
                                screenshot=screenshot_path
                            )
                        
                        step_results.append(step_result)

                    # 页面步骤执行完毕后，等待页面稳定（处理可能的页面跳转）
                    try:
                        await page.wait_for_load_state("load", timeout=10000)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        logger.debug(f"页面步骤 {page_step.page_name} 执行后等待页面稳定超时，继续执行")

                duration = time.time() - start_time
                status = 'success' if failed_steps == 0 else 'failed'
                message = f"用例执行{'成功' if status == 'success' else '失败'}: 通过 {passed_steps}/{total_steps}"
                logger.info(f"✅ {message}" if status == 'success' else f"❌ {message}")
                
                # 获取 trace 文件路径（会在 browser_session_with_trace 结束时设置）
                trace_path = None
            
            # 会话结束后获取 trace 路径
            trace_path = self.get_current_trace_path()
            if trace_path:
                logger.info(f"用例执行 Trace 已记录: {trace_path}")
            
            return CaseResultModel(
                case_id=config.case_id,
                status=status,
                message=message,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps,
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"用例执行异常: {error_msg}\n{traceback.format_exc()}")
            
            # 尝试获取 trace 路径（可能已保存）
            trace_path = self.get_current_trace_path()
            
            return CaseResultModel(
                case_id=config.case_id,
                status='failed',
                message=error_msg,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps + (total_steps - passed_steps - failed_steps),
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )

    async def execute_page_step(self, config: PageStepConfig) -> list[StepResultModel]:
        """执行单个页面步骤（包含多个操作）- 使用同一个浏览器会话"""
        step_results = []
        
        try:
            async with self.browser_session() as page:
                logger.info(f"开始执行页面步骤: {config.page_name}")
                
                # 导航到页面
                if config.page_url:
                    nav_start = time.time()
                    await page.goto(config.page_url)
                    await page.wait_for_load_state("domcontentloaded")
                    logger.debug(f"页面导航 {config.page_name} 耗时 {time.time() - nav_start:.2f}s")
                
                # 执行页面内的所有步骤
                for step in config.steps:
                    step_start = time.time()
                    try:
                        success, message, step_screenshot = await self._execute_step(page, step)
                        step_duration = time.time() - step_start

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='success' if success else 'failed',
                            message=message,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=success,
                            screenshot=step_screenshot
                        )
                        step_results.append(step_result)

                        if success:
                            logger.debug(f"  ✅ {step.description or step.operation_type}")
                        else:
                            logger.warning(f"  ❌ {step.description or step.operation_type}: {message}")
                            # 失败时额外截图
                            if not step_screenshot:
                                screenshot_path = f"{self.screenshot_dir}/fail_ps_{config.page_step_id}_{step.step_id}.png"
                                await page.screenshot(path=screenshot_path)
                                step_result.screenshot = screenshot_path
                            break  # 步骤失败时停止执行后续步骤

                    except Exception as step_error:
                        step_duration = time.time() - step_start
                        error_msg = str(step_error)
                        logger.error(f"  ❌ {step.description or step.operation_type}: {error_msg}")

                        # 失败时截图
                        try:
                            screenshot_path = f"{self.screenshot_dir}/error_ps_{config.page_step_id}_{step.step_id}.png"
                            await page.screenshot(path=screenshot_path)
                        except:
                            screenshot_path = None

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='failed',
                            message=error_msg,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=False,
                            screenshot=screenshot_path
                        )
                        step_results.append(step_result)
                        break  # 步骤失败时停止执行后续步骤
                        
        except Exception as e:
            logger.error(f"页面步骤执行异常: {e}\n{traceback.format_exc()}")
            # 如果连浏览器都打不开，返回一个失败结果
            if not step_results:
                step_results.append(StepResultModel(
                    step_id=0,
                    status='failed',
                    message=str(e),
                    duration=0,
                    element_found=False
                ))

        return step_results

    async def _execute_case_on_context(
        self,
        context: BrowserContext,
        config: TestCaseConfig,
        trace_enabled: bool = False
    ) -> CaseResultModel:
        """在独立上下文中执行用例（用于并发执行）"""
        start_time = time.time()
        step_results = []
        passed_steps = 0
        failed_steps = 0
        total_steps = sum(len(ps.steps) for ps in config.page_steps)
        trace_path = None

        try:
            # 启动 Trace
            if trace_enabled:
                await context.tracing.start(
                    screenshots=self.trace_screenshots,
                    snapshots=self.trace_snapshots,
                    sources=self.trace_sources,
                )

            page = await context.new_page()
            page.set_default_timeout(self.action_timeout)

            logger.info(f"[并发] 开始执行用例: {config.case_name}")

            # 浏览器启动后，立即导航到环境配置的 base_url
            base_url = ''
            if config.env_config:
                base_url = config.env_config.get('base_url', '') or ''
            if base_url:
                logger.info(f"[并发] 导航到环境 base_url: {base_url}")
                await page.goto(base_url, wait_until="networkidle")

            for page_step in config.page_steps:
                if self._stop_requested:
                    raise Exception("用例被手动停止")

                logger.info(f"[并发] 执行页面步骤: {page_step.page_name}")

                # 检测页面跳转：仅当下一个页面 URL 与当前不同时才等待
                if page_step.page_url:
                    current_url = page.url
                    expected_url = page_step.page_url.rstrip('/')

                    # 只有当期望的 URL 与当前 URL 不同时，才等待跳转
                    if expected_url not in current_url:
                        try:
                            # 短暂等待，检测是否有 URL 变化
                            await page.wait_for_url(
                                lambda url: url != current_url,
                                timeout=2000
                            )
                            logger.debug(f"[并发] 检测到页面跳转: {current_url} -> {page.url}")
                        except Exception:
                            # 没有页面跳转是正常情况
                            pass

                # 执行页面内的步骤
                for step in page_step.steps:
                    if self._stop_requested:
                        raise Exception("用例被手动停止")

                    step_start = time.time()
                    try:
                        success, message, step_screenshot = await self._execute_step(page, step)
                        step_duration = time.time() - step_start

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='success' if success else 'failed',
                            message=message,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=success,
                            screenshot=step_screenshot
                        )

                        if success:
                            passed_steps += 1
                        else:
                            failed_steps += 1
                            if not step_screenshot:
                                screenshot_path = f"{self.screenshot_dir}/fail_{config.case_id}_{step.step_id}.png"
                                await page.screenshot(path=screenshot_path)
                                step_result.screenshot = screenshot_path

                    except Exception as step_error:
                        step_duration = time.time() - step_start
                        failed_steps += 1
                        error_msg = str(step_error)

                        try:
                            screenshot_path = f"{self.screenshot_dir}/error_{config.case_id}_{step.step_id}.png"
                            await page.screenshot(path=screenshot_path)
                        except:
                            screenshot_path = None

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='failed',
                            message=error_msg,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=False,
                            screenshot=screenshot_path
                        )

                    step_results.append(step_result)

                # 页面步骤执行完毕后，等待页面稳定（处理可能的页面跳转）
                try:
                    await page.wait_for_load_state("load", timeout=10000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    logger.debug(f"[并发] 页面步骤 {page_step.page_name} 执行后等待页面稳定超时，继续执行")

            duration = time.time() - start_time
            status = 'success' if failed_steps == 0 else 'failed'
            message = f"用例执行{'成功' if status == 'success' else '失败'}: 通过 {passed_steps}/{total_steps}"

            # 保存 Trace
            if trace_enabled:
                trace_path = f"{self.trace_dir}/case_{config.case_id}_{int(time.time())}.zip"
                await context.tracing.stop(path=trace_path)

            await page.close()

            logger.info(f"[并发] {'✅' if status == 'success' else '❌'} {message}")

            return CaseResultModel(
                case_id=config.case_id,
                status=status,
                message=message,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps,
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"[并发] 用例执行异常: {error_msg}")

            # 尝试保存 Trace
            if trace_enabled:
                try:
                    trace_path = f"{self.trace_dir}/case_{config.case_id}_{int(time.time())}.zip"
                    await context.tracing.stop(path=trace_path)
                except:
                    pass

            return CaseResultModel(
                case_id=config.case_id,
                status='failed',
                message=error_msg,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps + (total_steps - passed_steps - failed_steps),
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )

    async def execute_batch_concurrent(
        self,
        configs: list[TestCaseConfig],
        max_concurrent: int = 3,
        on_result = None
    ) -> list[CaseResultModel]:
        """并发执行多个用例

        Args:
            configs: 用例配置列表
            max_concurrent: 最大并发数
            on_result: 单个用例完成时的回调函数 (可选)

        Returns:
            用例执行结果列表
        """
        if not configs:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        # 确保浏览器已初始化（非持久化模式）
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        browser_launcher = getattr(self._playwright, self.browser_type)
        browser = await browser_launcher.launch(
            headless=self.headless,
            timeout=self.launch_timeout,
        )

        logger.info(f"[并发执行] 开始执行 {len(configs)} 个用例, 最大并发数: {max_concurrent}")

        async def run_with_limit(config: TestCaseConfig):
            async with semaphore:
                # 每个用例独立的浏览器上下文
                context = await browser.new_context()
                try:
                    result = await self._execute_case_on_context(
                        context,
                        config,
                        trace_enabled=self.trace_enabled
                    )
                    if on_result:
                        await on_result(result)
                    return result
                finally:
                    await context.close()

        try:
            # 并发执行所有用例
            results = await asyncio.gather(
                *[run_with_limit(c) for c in configs],
                return_exceptions=True
            )

            # 处理异常结果
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    final_results.append(CaseResultModel(
                        case_id=configs[i].case_id,
                        status='failed',
                        message=str(result),
                        total_steps=0,
                        passed_steps=0,
                        failed_steps=0,
                        duration=0,
                        steps=[]
                    ))
                else:
                    final_results.append(result)

            logger.info(f"[并发执行] 完成, 成功: {sum(1 for r in final_results if r.status == 'success')}/{len(final_results)}")
            return final_results

        finally:
            await browser.close()
