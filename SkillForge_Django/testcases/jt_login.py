from playwright.sync_api import sync_playwright, expect
import random
import os
import random
import io
import cv2
import numpy as np
from PIL import Image


# ======================= 辅助函数 =======================
def safe_text(text):
    """清理文本，去除空白和换行"""
    return text.strip() if text else ""


def collect_page_texts(page):
    """
    收集当前页面中所有可见元素的中文文本
    返回: set of strings
    """
    texts = set()
    # 获取所有可见元素（排除 script/style 等）
    elements = page.locator("body *").all()
    for el in elements:
        try:
            if not el.is_visible():
                continue
            text = safe_text(el.inner_text())
            # 只保留包含中文的文本（可根据需要调整）
            if text and any('\u4e00' <= c <= '\u9fff' for c in text):
                texts.add(text)
        except:
            pass
    return texts


def collect_menu_texts(page):
    """
    遍历所有菜单（包括子菜单），点击每个菜单项，收集当前页面中的中文文本
    返回: list of strings (所有收集到的文本)
    """
    collected_texts = set()

    # 递归处理菜单项
    def process_menu(menu_item, parent_prefix=""):
        try:
            # 获取菜单项的文本（优先使用 antd 的标题类，否则取 div/span）
            title_span = menu_item.locator("span.ant-menu-title-content").first
            if title_span.count() == 0:
                title_span = menu_item.locator("xpath=./div/span").first
            text = safe_text(title_span.inner_text())
            if not text:
                return

            full_text = f"{parent_prefix}{text}" if parent_prefix else text
            collected_texts.add(full_text)
            print(f"  📝 菜单: {full_text}")

            # 检查是否有子菜单
            sub_ul = menu_item.locator("xpath=./ul").first
            if sub_ul.count() > 0:
                # 如果子菜单未展开，点击菜单项展开
                if not sub_ul.is_visible():
                    menu_item.locator("xpath=./div").first.click()
                    page.wait_for_timeout(500)

                # 处理所有子菜单项
                sub_items = sub_ul.locator("xpath=./li").all()
                for sub in sub_items:
                    process_menu(sub, f"{full_text} > ")
            else:
                # 叶子菜单项：点击，等待页面加载，收集页面文本
                try:
                    click_target = title_span if title_span.count() > 0 else menu_item.locator("xpath=./div").first
                    click_target.click()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(1000)  # 等待动态内容

                    page_texts = collect_page_texts(page)
                    for pt in page_texts:
                        collected_texts.add(pt)
                        print(f"    📄 页面文本: {pt}")
                except Exception as e:
                    print(f"    ⚠️ 点击叶子菜单失败: {e}")
        except Exception as e:
            print(f"  ⚠️ 处理菜单项出错: {e}")

    # 获取所有顶级菜单项（使用提供的 XPath 索引）
    for i in range(1, 7):
        menu_item = page.locator(f"xpath=//*[@id='app']/section/section/aside/div/div/ul/li[{i}]")
        if menu_item.count() > 0:
            process_menu(menu_item)

    return list(collected_texts)


def switch_language(page, target_lang="EN"):
    """切换到指定语言（EN 或 CN）"""
    # 点击语言切换按钮（XPath）
    lang_btn = page.locator("xpath=//*[@id='app']/section/header/div/a").first
    lang_btn.click()
    page.wait_for_timeout(500)

    # 根据目标语言选择对应的菜单项（XPath）
    if target_lang == "EN":
        lang_option = page.locator("xpath=/html/body/div[2]/div/div/div/ul/li[2]/span").first
    else:
        lang_option = page.locator("xpath=/html/body/div[2]/div/div/div/ul/li[1]/span").first
    lang_option.click()

    # 等待页面刷新
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)  # 额外等待确保语言切换完成


def find_untranstaled_elements(page, chinese_texts):
    """
    遍历页面所有元素，找出文本内容与 chinese_texts 中任一完全相同的元素
    返回: 列表，每个元素为 (element, matched_text)
    """
    matched = []
    # 获取页面中所有有文本内容的元素（排除script/style等）
    elements = page.locator("body *").all()
    print(f"🔍 扫描页面中所有元素（共 {len(elements)} 个）")

    for el in elements:
        try:
            # 只考虑可见且包含文本的元素
            if not el.is_visible():
                continue
            text = safe_text(el.inner_text())
            if not text:
                continue
            # 检查是否与中文列表中的某个完全匹配
            if text in chinese_texts:
                matched.append((el, text))
                print(f"  ⚠️ 发现未翻译文本: '{text}'")
        except:
            # 忽略某些元素可能不可交互导致的异常
            pass

    return matched


def highlight_and_screenshot(page, element, text, index, save_dir="C:\\doc"):
    """高亮元素（仅红色边框）并截图整个窗口"""
    try:
        # 高亮：仅添加红色边框，不改变背景
        original_border = element.evaluate("el => el.style.border")
        element.evaluate("el => { el.style.border = '3px solid red'; }")

        # 确保目录存在
        os.makedirs(save_dir, exist_ok=True)

        # 生成安全的文件名
        safe_name = text.replace("\\", "_").replace("/", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_")
        filename = f"{index:03d}_{safe_name}.png"
        filepath = os.path.join(save_dir, filename)

        # 滚动到元素，使其在视口中可见
        element.scroll_into_view_if_needed()
        page.wait_for_timeout(200)  # 等待滚动完成

        # 截图当前视口（窗口尺寸），不滚动整个页面
        page.screenshot(path=filepath, full_page=False)
        print(f"  📸 截图已保存: {filepath}")

        # 恢复原样式
        element.evaluate(f"el => {{ el.style.border = '{original_border}'; }}")
    except Exception as e:
        print(f"  ❌ 高亮/截图失败: {e}")

# ======================= 滑块缺口识别（Canny边缘强化 + 严格区域限制）=======================
def get_gap_offset_opencv(bg_img_pil, gap_img_pil, search_start=200, search_end=340):
    """
    使用 OpenCV 边缘检测 + 模板匹配识别缺口位置
    - search_start: 搜索起始 X 坐标（避开左侧滑块）
    - search_end: 搜索结束 X 坐标
    """
    try:
        # 转换为 OpenCV 格式
        bg_cv = cv2.cvtColor(np.array(bg_img_pil), cv2.COLOR_RGB2BGR)
        gap_cv = cv2.cvtColor(np.array(gap_img_pil), cv2.COLOR_RGB2BGR)

        # 转为灰度
        bg_gray = cv2.cvtColor(bg_cv, cv2.COLOR_BGR2GRAY)
        gap_gray = cv2.cvtColor(gap_cv, cv2.COLOR_BGR2GRAY)

        # 高斯模糊去噪
        bg_gray = cv2.GaussianBlur(bg_gray, (3, 3), 0)
        gap_gray = cv2.GaussianBlur(gap_gray, (3, 3), 0)

        # Canny 边缘检测，突出缺口白边轮廓
        bg_edges = cv2.Canny(bg_gray, 50, 150)
        gap_edges = cv2.Canny(gap_gray, 50, 150)

        h_gap, w_gap = gap_edges.shape
        h_bg, w_bg = bg_edges.shape

        # 安全限制搜索区域
        max_x = w_bg - w_gap
        if search_start > max_x:
            search_start = max(0, max_x - 50)
        if search_end > max_x:
            search_end = max_x

        roi = bg_edges[:, search_start:search_end + 1]

        # 模板匹配
        result = cv2.matchTemplate(roi, gap_edges, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        offset_in_roi = max_loc[0]
        offset_x = search_start + offset_in_roi
        match_rate = max_val

        print(f"🔍 模板匹配结果 | 位置: {offset_x}px | 匹配度: {match_rate:.2%}")

        # 校验：如果位置落在左侧滑块区域（<200）且匹配度低于0.1，视为误匹配
        if offset_x < 200 and match_rate < 0.2:
            print("⚠️ 识别位置在左侧滑块区域，误匹配，刷新重试")
            return None

        # 匹配度阈值（Canny后匹配度通常较低，0.45即可）
        if match_rate < 0.2:
            print("⚠️ 匹配度过低，可能识别失败")
            return None

        return offset_x

    except Exception as e:
        print(f"❌ OpenCV 识别异常: {e}")
        return None


def get_gap_offset(page, bg_selector=".verify-img-panel", gap_selector=".verify-sub-block"):
    """
    获取缺口在背景图中的绝对像素位置
    """
    try:
        bg_element = page.locator(bg_selector).first
        gap_element = page.locator(gap_selector).first
        bg_element.wait_for(state="visible", timeout=5000)
        gap_element.wait_for(state="visible", timeout=5000)

        bg_screenshot = bg_element.screenshot()
        gap_screenshot = gap_element.screenshot()

        bg_img = Image.open(io.BytesIO(bg_screenshot))
        gap_img = Image.open(io.BytesIO(gap_screenshot))

        offset = get_gap_offset_opencv(bg_img, gap_img, search_start=200, search_end=340)
        return offset

    except Exception as e:
        print(f"❌ 获取缺口位置失败: {e}")
        return None


# ======================= 滑块拖动（人类化轨迹 + 终点随机偏移）=======================
def human_like_slider(page, max_retries=20):
    """
    模拟人类拖动滑块
    """
    VERIFY_BOX_SELECTOR = ".verifybox"
    SLIDER_BLOCK_SELECTOR = ".verify-move-block"
    REFRESH_BTN_SELECTOR = ".verify-refresh"

    for attempt in range(max_retries):
        try:
            print(f"\n🔄 滑块验证尝试 {attempt + 1}/{max_retries}")

            # 等待验证弹窗和滑块出现
            page.wait_for_selector(VERIFY_BOX_SELECTOR, state="visible", timeout=5000)
            slider = page.locator(SLIDER_BLOCK_SELECTOR).first
            slider.wait_for(state="visible", timeout=5000)

            # 1. 获取缺口位置
            gap_abs_x = get_gap_offset(page)
            if gap_abs_x is None:
                print("ℹ️ 识别失败，刷新验证码")
                page.locator(REFRESH_BTN_SELECTOR).click()
                page.wait_for_timeout(500)
                continue

            # 2. 获取滑块和背景图容器的屏幕坐标
            slider_box = slider.bounding_box()
            if not slider_box:
                print("❌ 无法获取滑块位置，刷新重试")
                page.locator(REFRESH_BTN_SELECTOR).click()
                page.wait_for_timeout(500)
                continue

            bg_container = page.locator(".verify-img-panel").first
            bg_box = bg_container.bounding_box()
            if not bg_box:
                print("❌ 无法获取背景图容器位置，刷新重试")
                page.locator(REFRESH_BTN_SELECTOR).click()
                page.wait_for_timeout(500)
                continue

            # 3. 计算需要移动的距离（屏幕坐标差）
            start_x = slider_box["x"] + slider_box["width"] / 2
            start_y = slider_box["y"] + slider_box["height"] / 2
            target_screen_x = bg_box["x"] + gap_abs_x + (slider_box["width"] / 2)  # 缺口中心点 X
            distance = target_screen_x - start_x

            print(f"📏 移动距离: {distance:.1f}px (缺口绝对坐标: {gap_abs_x}px)")

            # 4. 人类式移动到起点
            page.mouse.move(
                start_x + random.randint(-10, 10),
                start_y + random.randint(-3, 3),
                steps=random.randint(6, 10)
            )
            page.wait_for_timeout(random.randint(50, 100))
            page.mouse.move(start_x, start_y, steps=random.randint(3, 5))
            page.wait_for_timeout(random.randint(30, 60))

            # 5. 按下鼠标
            page.mouse.down()
            page.wait_for_timeout(random.randint(40, 80))

            # 6. 自然轨迹：缓动 + 随机扰动
            total_steps = random.randint(20, 30)
            for i in range(total_steps):
                progress = i / total_steps
                # easeOutCubic 缓动
                ease_progress = 1 - (1 - progress) ** 3
                next_x = start_x + distance * ease_progress

                # 随机扰动，越到终点扰动越小
                x_offset = random.uniform(-1.5, 1.5) * (1 - ease_progress)
                next_x += x_offset
                next_y = start_y + random.uniform(-2, 2)

                page.mouse.move(next_x, next_y, steps=1)

                # 随机短暂停顿
                if random.random() < 0.1:
                    page.wait_for_timeout(random.randint(2, 6))

            # 7. 终点微调：增加 ±2px 随机偏移，提高容错率
            final_target_x = target_screen_x + random.uniform(-2, 2)
            overshoot = random.randint(1, 3)
            page.mouse.move(final_target_x + overshoot, start_y, steps=random.randint(1, 2))
            page.wait_for_timeout(random.randint(10, 25))
            page.mouse.move(final_target_x, start_y, steps=1)
            page.wait_for_timeout(random.randint(20, 50))

            # 8. 松开鼠标
            page.mouse.up()
            page.wait_for_timeout(random.randint(60, 100))

            # 9. 验证结果
            try:
                page.wait_for_selector(VERIFY_BOX_SELECTOR, state="hidden", timeout=2500)
                print("🎉 滑块验证成功！")
                return True
            except:
                print("❌ 验证失败，刷新重试")
                page.locator(REFRESH_BTN_SELECTOR).click()
                page.wait_for_timeout(500)
                continue

        except Exception as e:
            print(f"⚠️ 滑块验证异常: {e}")
            try:
                page.locator(REFRESH_BTN_SELECTOR).click()
                page.wait_for_timeout(500)
            except:
                pass
            continue

    print("❌ 滑块验证尝试全部失败")
    return False


# ======================= 主流程 ========================
def main():
    with sync_playwright() as p:
        # 最大化浏览器窗口
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized", "--window-position=0,0"]
        )
        context = browser.new_context(viewport=None)  # 视口跟随窗口大小
        page = context.new_page()
        print("✅ 浏览器已最大化")

        # 确保截图目录存在
        screenshot_dir = "login_screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        step = 0
        try:
            step += 1
            # 使用马来西亚站点URL（用户执行时使用的站点）
            login_url = "https://demo-station-admin.jtexpress.my"
            print(f"🔄 步骤{step}: 正在导航到登录页面: {login_url}")
            page.goto(login_url, wait_until="networkidle", timeout=30000)
            
            # 等待页面加载完成
            page.wait_for_timeout(2000)
            
            # 验证页面是否成功加载（不依赖标题，因为标题可能不同）
            if page.url == "about:blank":
                print("❌ 页面导航失败，当前页面为空白页")
                # 重试导航
                print("🔄 重试导航到登录页面...")
                page.goto(login_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
            
            print(f"✅ 步骤{step}: 打开登录页面成功")
            screenshot_path = os.path.join(screenshot_dir, f"step{step}_open_login_page.png")
            page.screenshot(path=screenshot_path)
            print(f"📸 截图已保存: {screenshot_path}")

            step += 1
            print(f"🔄 步骤{step}: 输入用户名和密码")
            
            # 支持多种可能的用户名输入框定位方式
            account_input = None
            input_selectors = [
                page.get_by_role("textbox", name="请输入账号"),
                page.get_by_role("textbox", name="Username"),
                page.locator("input[type='text']").first,
                page.locator("input[name='username']").first,
                page.locator("input[placeholder*='账号']").first,
                page.locator("input[placeholder*='Username']").first
            ]
            
            for selector in input_selectors:
                try:
                    selector.wait_for(state="visible", timeout=3000)
                    account_input = selector
                    break
                except:
                    continue
            
            if account_input:
                account_input.fill("JT820024")
                print("✅ 用户名输入成功")
            else:
                print("❌ 未找到用户名输入框")

            # 支持多种可能的密码输入框定位方式
            password_input = None
            password_selectors = [
                page.get_by_role("textbox", name="请输入密码"),
                page.get_by_role("textbox", name="Password"),
                page.locator("input[type='password']").first,
                page.locator("input[name='password']").first,
                page.locator("input[placeholder*='密码']").first,
                page.locator("input[placeholder*='Password']").first
            ]
            
            for selector in password_selectors:
                try:
                    selector.wait_for(state="visible", timeout=3000)
                    password_input = selector
                    break
                except:
                    continue
            
            if password_input:
                password_input.fill("Aa123456")
                print("✅ 密码输入成功")
            else:
                print("❌ 未找到密码输入框")
            
            print(f"✅ 步骤{step}: 输入用户名和密码完成")
            screenshot_path = os.path.join(screenshot_dir, f"step{step}_input_credentials.png")
            page.screenshot(path=screenshot_path)
            print(f"📸 截图已保存: {screenshot_path}")

            step += 1
            print(f"🔄 步骤{step}: 点击登录按钮")
            
            # 支持多种可能的登录按钮定位方式
            login_button = None
            button_selectors = [
                page.get_by_role("button", name="登录"),
                page.get_by_role("button", name="Login"),
                page.locator("button[type='submit']").first,
                page.locator("button:has-text('登录')").first,
                page.locator("button:has-text('Login')").first,
                page.locator(".login-btn").first
            ]
            
            for selector in button_selectors:
                try:
                    selector.wait_for(state="visible", timeout=5000)
                    login_button = selector
                    break
                except:
                    continue
            
            if login_button:
                login_button.click()
                print(f"✅ 步骤{step}: 点击登录按钮成功")
            else:
                print("❌ 未找到登录按钮")
            
            screenshot_path = os.path.join(screenshot_dir, f"step{step}_click_login.png")
            page.screenshot(path=screenshot_path)
            print(f"📸 截图已保存: {screenshot_path}")

            step += 1
            print(f"🔄 步骤{step}: 检测安全验证")
            page.wait_for_timeout(1000)
            
            # 支持多种安全验证检测方式
            verify_box = page.locator(".verifybox")
            verify_text = page.locator("text=请完成安全验证")
            verify_text_en = page.locator("text=Please complete security verification")
            
            has_verification = False
            try:
                has_verification = (verify_box.is_visible() and 
                                  (verify_text.is_visible() or verify_text_en.is_visible()))
            except:
                pass

            if has_verification:
                print("ℹ️ 检测到安全验证，开始处理滑块（最多20次重试）")
                slider_success = human_like_slider(page, max_retries=20)
                if not slider_success:
                    print("❌ 滑块验证失败，脚本终止")
                    return
            else:
                print("ℹ️ 未检测到安全验证，跳过滑块处理")

            step += 1
            print(f"🔄 步骤{step}: 验证登录结果")
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(2000)
            
            screenshot_path = os.path.join(screenshot_dir, f"step{step}_login_final_result.png")
            page.screenshot(path=screenshot_path)
            print(f"📸 截图已保存: {screenshot_path}")

            if "login" not in page.url.lower():
                print("🎉 登录成功！")
            else:
                print("⚠️ 仍在登录页，请检查截图")

            # ---------- 步骤5：登录后验证 ----------
            step += 1
            print(f"� 步骤{step}: 验证登录成功后的页面状态")
            
            # 检查是否跳转到主页或仪表盘
            dashboard_selectors = [
                page.locator("text=Dashboard"),
                page.locator("text=仪表盘"),
                page.locator("text=首页"),
                page.locator(".ant-layout-content").first
            ]
            
            is_logged_in = False
            for selector in dashboard_selectors:
                try:
                    if selector.is_visible():
                        is_logged_in = True
                        break
                except:
                    continue
            
            if is_logged_in:
                print("🎉 登录验证通过！已成功进入系统")
            else:
                print("⚠️ 登录验证不确定，请手动检查")

            print("\n✅ 所有登录任务完成！")

        except Exception as e:
            print(f"❌ 脚本异常: {e}")
            try:
                screenshot_path = os.path.join(screenshot_dir, f"step{step}_error.png")
                page.screenshot(path=screenshot_path)
                print(f"📸 错误截图已保存: {screenshot_path}")
            except:
                pass

        finally:
            print("ℹ️ 浏览器将在5秒后关闭...")
            page.wait_for_timeout(5000)
            browser.close()


if __name__ == "__main__":
    main()