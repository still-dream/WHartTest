"""
滑块验证码识别和处理模块

提供滑块验证码的识别和自动处理功能，适用于各种滑块验证场景。
同时提供脚本内联版本，用于生成自包含的自动化脚本。
"""

import random
import io
import cv2
import numpy as np
from PIL import Image


def get_gap_offset_opencv(bg_img_pil, gap_img_pil, search_start=200, search_end=340):
    """
    使用 OpenCV 边缘检测 + 模板匹配识别缺口位置
    
    Args:
        bg_img_pil: PIL Image 对象，背景图
        gap_img_pil: PIL Image 对象，缺口图（滑块）
        search_start: 搜索起始 X 坐标（避开左侧滑块），默认 200
        search_end: 搜索结束 X 坐标，默认 340
    
    Returns:
        int: 缺口在背景图中的 X 坐标位置，识别失败返回 None
    """
    try:
        bg_cv = cv2.cvtColor(np.array(bg_img_pil), cv2.COLOR_RGB2BGR)
        gap_cv = cv2.cvtColor(np.array(gap_img_pil), cv2.COLOR_RGB2BGR)

        bg_gray = cv2.cvtColor(bg_cv, cv2.COLOR_BGR2GRAY)
        gap_gray = cv2.cvtColor(gap_cv, cv2.COLOR_BGR2GRAY)

        bg_gray = cv2.GaussianBlur(bg_gray, (3, 3), 0)
        gap_gray = cv2.GaussianBlur(gap_gray, (3, 3), 0)

        bg_edges = cv2.Canny(bg_gray, 50, 150)
        gap_edges = cv2.Canny(gap_gray, 50, 150)

        h_gap, w_gap = gap_edges.shape
        h_bg, w_bg = bg_edges.shape

        max_x = w_bg - w_gap
        if search_start > max_x:
            search_start = max(0, max_x - 50)
        if search_end > max_x:
            search_end = max_x

        roi = bg_edges[:, search_start:search_end + 1]

        result = cv2.matchTemplate(roi, gap_edges, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        offset_in_roi = max_loc[0]
        offset_x = search_start + offset_in_roi
        match_rate = max_val

        print(f"🔍 模板匹配结果 | 位置: {offset_x}px | 匹配度: {match_rate:.2%}")

        if offset_x < 200 and match_rate < 0.2:
            print("⚠️ 识别位置在左侧滑块区域，误匹配，刷新重试")
            return None

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
    
    Args:
        page: Playwright Page 对象
        bg_selector: 背景图元素的 CSS 选择器，默认 ".verify-img-panel"
        gap_selector: 缺口图元素的 CSS 选择器，默认 ".verify-sub-block"
    
    Returns:
        int: 缺口的 X 坐标位置，失败返回 None
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


def human_like_slider(
    page,
    verify_box_selector=".verifybox",
    slider_block_selector=".verify-move-block",
    refresh_btn_selector=".verify-refresh",
    bg_selector=".verify-img-panel",
    gap_selector=".verify-sub-block",
    max_retries=20
):
    """
    模拟人类拖动滑块完成验证
    
    Args:
        page: Playwright Page 对象
        verify_box_selector: 验证框容器的 CSS 选择器
        slider_block_selector: 滑块元素的 CSS 选择器
        refresh_btn_selector: 刷新按钮的 CSS 选择器
        bg_selector: 背景图元素的 CSS 选择器
        gap_selector: 缺口图元素的 CSS 选择器
        max_retries: 最大重试次数，默认 20
    
    Returns:
        bool: 验证成功返回 True，失败返回 False
    """
    for attempt in range(max_retries):
        try:
            print(f"\n🔄 滑块验证尝试 {attempt + 1}/{max_retries}")

            page.wait_for_selector(verify_box_selector, state="visible", timeout=5000)
            slider = page.locator(slider_block_selector).first
            slider.wait_for(state="visible", timeout=5000)

            gap_abs_x = get_gap_offset(page, bg_selector, gap_selector)
            if gap_abs_x is None:
                print("ℹ️ 识别失败，刷新验证码")
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
                continue

            slider_box = slider.bounding_box()
            if not slider_box:
                print("❌ 无法获取滑块位置，刷新重试")
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
                continue

            bg_container = page.locator(bg_selector).first
            bg_box = bg_container.bounding_box()
            if not bg_box:
                print("❌ 无法获取背景图容器位置，刷新重试")
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
                continue

            start_x = slider_box["x"] + slider_box["width"] / 2
            start_y = slider_box["y"] + slider_box["height"] / 2
            target_screen_x = bg_box["x"] + gap_abs_x + (slider_box["width"] / 2)
            distance = target_screen_x - start_x

            print(f"📏 移动距离: {distance:.1f}px (缺口绝对坐标: {gap_abs_x}px)")

            page.mouse.move(
                start_x + random.randint(-10, 10),
                start_y + random.randint(-3, 3),
                steps=random.randint(6, 10)
            )
            page.wait_for_timeout(random.randint(50, 100))
            page.mouse.move(start_x, start_y, steps=random.randint(3, 5))
            page.wait_for_timeout(random.randint(30, 60))

            page.mouse.down()
            page.wait_for_timeout(random.randint(40, 80))

            total_steps = random.randint(20, 30)
            for i in range(total_steps):
                progress = i / total_steps
                ease_progress = 1 - (1 - progress) ** 3
                next_x = start_x + distance * ease_progress

                x_offset = random.uniform(-1.5, 1.5) * (1 - ease_progress)
                next_x += x_offset
                next_y = start_y + random.uniform(-2, 2)

                page.mouse.move(next_x, next_y, steps=1)

                if random.random() < 0.1:
                    page.wait_for_timeout(random.randint(2, 6))

            final_target_x = target_screen_x + random.uniform(-2, 2)
            overshoot = random.randint(1, 3)
            page.mouse.move(final_target_x + overshoot, start_y, steps=random.randint(1, 2))
            page.wait_for_timeout(random.randint(10, 25))
            page.mouse.move(final_target_x, start_y, steps=1)
            page.wait_for_timeout(random.randint(20, 50))

            page.mouse.up()
            page.wait_for_timeout(random.randint(60, 100))

            try:
                page.wait_for_selector(verify_box_selector, state="hidden", timeout=2500)
                print("🎉 滑块验证成功！")
                return True
            except:
                print("❌ 验证失败，刷新重试")
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
                continue

        except Exception as e:
            print(f"⚠️ 滑块验证异常: {e}")
            try:
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
            except:
                pass
            continue

    print("❌ 滑块验证尝试全部失败")
    return False


def handle_slider_captcha(
    page,
    verify_box_selector=".verifybox",
    verify_text_selector="text=请完成安全验证",
    slider_block_selector=".verify-move-block",
    refresh_btn_selector=".verify-refresh",
    bg_selector=".verify-img-panel",
    gap_selector=".verify-sub-block",
    max_retries=20
):
    """
    检测并处理滑块验证码（自动检测是否需要验证）
    
    同时检测验证框和验证提示文字，双重确认后才触发滑块处理，
    避免误判导致不必要的滑块操作。
    
    Args:
        page: Playwright Page 对象
        verify_box_selector: 验证框容器的 CSS 选择器
        verify_text_selector: 验证提示文字的选择器，如 "text=请完成安全验证"
        slider_block_selector: 滑块元素的 CSS 选择器
        refresh_btn_selector: 刷新按钮的 CSS 选择器
        bg_selector: 背景图元素的 CSS 选择器
        gap_selector: 缺口图元素的 CSS 选择器
        max_retries: 最大重试次数，默认 20
    
    Returns:
        bool: 验证成功或无需验证返回 True，验证失败返回 False
    """
    try:
        page.wait_for_timeout(500)
        verify_box = page.locator(verify_box_selector)
        verify_text = page.locator(verify_text_selector) if verify_text_selector else None

        box_visible = verify_box.is_visible()
        text_visible = verify_text.is_visible() if verify_text else True

        if box_visible and text_visible:
            print("ℹ️ 检测到安全验证，开始处理滑块（最多{}次重试）".format(max_retries))
            slider_success = human_like_slider(
                page,
                verify_box_selector,
                slider_block_selector,
                refresh_btn_selector,
                bg_selector,
                gap_selector,
                max_retries
            )
            return slider_success
        else:
            print("ℹ️ 未检测到安全验证，跳过滑块处理")
            return True

    except Exception as e:
        print(f"⚠️ 检测滑块验证异常: {e}")
        return False


def get_inline_slider_code():
    """
    返回滑块验证码处理的内联代码字符串，用于生成自包含的自动化脚本。

    当生成的脚本需要在无法 import slider_captcha 的独立环境中运行时，
    可以将此代码内联到脚本中，实现与 slider_captcha.py 完全一致的逻辑。

    Returns:
        str: 可嵌入脚本的 Python 代码字符串
    """
    return '''
import random
import io
import cv2
import numpy as np
from PIL import Image


def _get_gap_offset_opencv(bg_img_pil, gap_img_pil, search_start=200, search_end=340):
    try:
        bg_cv = cv2.cvtColor(np.array(bg_img_pil), cv2.COLOR_RGB2BGR)
        gap_cv = cv2.cvtColor(np.array(gap_img_pil), cv2.COLOR_RGB2BGR)
        bg_gray = cv2.GaussianBlur(cv2.cvtColor(bg_cv, cv2.COLOR_BGR2GRAY), (3, 3), 0)
        gap_gray = cv2.GaussianBlur(cv2.cvtColor(gap_cv, cv2.COLOR_BGR2GRAY), (3, 3), 0)
        bg_edges = cv2.Canny(bg_gray, 50, 150)
        gap_edges = cv2.Canny(gap_gray, 50, 150)
        h_gap, w_gap = gap_edges.shape
        h_bg, w_bg = bg_edges.shape
        max_x = w_bg - w_gap
        if search_start > max_x:
            search_start = max(0, max_x - 50)
        if search_end > max_x:
            search_end = max_x
        roi = bg_edges[:, search_start:search_end + 1]
        result = cv2.matchTemplate(roi, gap_edges, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        offset_x = search_start + max_loc[0]
        match_rate = max_val
        print(f"\\U0001f50d 模板匹配结果 | 位置: {offset_x}px | 匹配度: {match_rate:.2%}")
        if offset_x < 200 and match_rate < 0.2:
            print("\\u26a0\\ufe0f 识别位置在左侧滑块区域，误匹配，刷新重试")
            return None
        if match_rate < 0.2:
            print("\\u26a0\\ufe0f 匹配度过低，可能识别失败")
            return None
        return offset_x
    except Exception as e:
        print(f"\\u274c OpenCV 识别异常: {e}")
        return None


def _get_gap_offset(page, bg_selector=".verify-img-panel", gap_selector=".verify-sub-block"):
    try:
        bg_element = page.locator(bg_selector).first
        gap_element = page.locator(gap_selector).first
        bg_element.wait_for(state="visible", timeout=5000)
        gap_element.wait_for(state="visible", timeout=5000)
        bg_img = Image.open(io.BytesIO(bg_element.screenshot()))
        gap_img = Image.open(io.BytesIO(gap_element.screenshot()))
        return _get_gap_offset_opencv(bg_img, gap_img, search_start=200, search_end=340)
    except Exception as e:
        print(f"\\u274c 获取缺口位置失败: {e}")
        return None


def _human_like_slider(page, verify_box_selector=".verifybox",
                        slider_block_selector=".verify-move-block",
                        refresh_btn_selector=".verify-refresh",
                        bg_selector=".verify-img-panel",
                        gap_selector=".verify-sub-block",
                        max_retries=20):
    for attempt in range(max_retries):
        try:
            print(f"\\n\\U0001f504 滑块验证尝试 {attempt + 1}/{max_retries}")
            page.wait_for_selector(verify_box_selector, state="visible", timeout=5000)
            slider = page.locator(slider_block_selector).first
            slider.wait_for(state="visible", timeout=5000)
            gap_abs_x = _get_gap_offset(page, bg_selector, gap_selector)
            if gap_abs_x is None:
                print("\\u2139\\ufe0f 识别失败，刷新验证码")
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
                continue
            slider_box = slider.bounding_box()
            if not slider_box:
                print("\\u274c 无法获取滑块位置，刷新重试")
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
                continue
            bg_box = page.locator(bg_selector).first.bounding_box()
            if not bg_box:
                print("\\u274c 无法获取背景图容器位置，刷新重试")
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
                continue
            start_x = slider_box["x"] + slider_box["width"] / 2
            start_y = slider_box["y"] + slider_box["height"] / 2
            target_screen_x = bg_box["x"] + gap_abs_x + (slider_box["width"] / 2)
            distance = target_screen_x - start_x
            print(f"\\U0001f4cf 移动距离: {distance:.1f}px (缺口绝对坐标: {gap_abs_x}px)")
            page.mouse.move(start_x + random.randint(-10, 10), start_y + random.randint(-3, 3), steps=random.randint(6, 10))
            page.wait_for_timeout(random.randint(50, 100))
            page.mouse.move(start_x, start_y, steps=random.randint(3, 5))
            page.wait_for_timeout(random.randint(30, 60))
            page.mouse.down()
            page.wait_for_timeout(random.randint(40, 80))
            total_steps = random.randint(20, 30)
            for i in range(total_steps):
                progress = i / total_steps
                ease_progress = 1 - (1 - progress) ** 3
                next_x = start_x + distance * ease_progress + random.uniform(-1.5, 1.5) * (1 - ease_progress)
                next_y = start_y + random.uniform(-2, 2)
                page.mouse.move(next_x, next_y, steps=1)
                if random.random() < 0.1:
                    page.wait_for_timeout(random.randint(2, 6))
            final_target_x = target_screen_x + random.uniform(-2, 2)
            overshoot = random.randint(1, 3)
            page.mouse.move(final_target_x + overshoot, start_y, steps=random.randint(1, 2))
            page.wait_for_timeout(random.randint(10, 25))
            page.mouse.move(final_target_x, start_y, steps=1)
            page.wait_for_timeout(random.randint(20, 50))
            page.mouse.up()
            page.wait_for_timeout(random.randint(60, 100))
            try:
                page.wait_for_selector(verify_box_selector, state="hidden", timeout=2500)
                print("\\U0001f389 滑块验证成功！")
                return True
            except:
                print("\\u274c 验证失败，刷新重试")
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
                continue
        except Exception as e:
            print(f"\\u26a0\\ufe0f 滑块验证异常: {e}")
            try:
                page.locator(refresh_btn_selector).click()
                page.wait_for_timeout(500)
            except:
                pass
            continue
    print("\\u274c 滑块验证尝试全部失败")
    return False


def _handle_slider_captcha(page, max_retries=20):
    try:
        page.wait_for_timeout(500)
        verify_box = page.locator(".verifybox")
        verify_text = page.locator("text=请完成安全验证")
        box_visible = verify_box.is_visible()
        text_visible = verify_text.is_visible()
        if box_visible and text_visible:
            print("ℹ️ 检测到安全验证，开始处理滑块（最多{}次重试）".format(max_retries))
            return _human_like_slider(page, max_retries=max_retries)
        else:
            print("ℹ️ 未检测到安全验证，跳过滑块处理")
            return True
    except Exception as e:
        print(f"⚠️ 检测滑块验证异常: {e}")
        return False
'''
