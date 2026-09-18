"""
页面操作工具模块

提供常用的页面操作方法，包括文本收集、菜单遍历、语言切换、元素查找等功能。
"""

import os
from PIL import Image


def safe_text(text):
    """
    清理文本，去除空白和换行
    
    Args:
        text: 原始文本
    
    Returns:
        str: 清理后的文本，如果输入为 None 返回空字符串
    """
    return text.strip() if text else ""


def collect_page_texts(page):
    """
    收集当前页面中所有可见元素的中文文本
    
    Args:
        page: Playwright Page 对象
    
    Returns:
        set: 包含所有可见中文文本的集合
    """
    texts = set()
    elements = page.locator("body *").all()
    
    for el in elements:
        try:
            if not el.is_visible():
                continue
            text = safe_text(el.inner_text())
            if text and any('\u4e00' <= c <= '\u9fff' for c in text):
                texts.add(text)
        except:
            pass
    
    return texts


def collect_menu_texts(page, menu_xpath_base="//*[@id='app']/section/section/aside/div/div/ul/li[{i}]"):
    """
    遍历所有菜单（包括子菜单），点击每个菜单项，收集当前页面中的中文文本
    
    Args:
        page: Playwright Page 对象
        menu_xpath_base: 菜单项的 XPath 基础模板，默认为 J&T 系统的菜单路径
    
    Returns:
        list: 所有收集到的文本列表
    """
    collected_texts = set()

    def process_menu(menu_item, parent_prefix=""):
        try:
            title_span = menu_item.locator("span.ant-menu-title-content").first
            if title_span.count() == 0:
                title_span = menu_item.locator("xpath=./div/span").first

            
            text = safe_text(title_span.inner_text())
            if not text:
                return

            full_text = f"{parent_prefix}{text}" if parent_prefix else text
            collected_texts.add(full_text)
            print(f"  📝 菜单: {full_text}")

            sub_ul = menu_item.locator("xpath=./ul").first
            if sub_ul.count() > 0:
                if not sub_ul.is_visible():
                    menu_item.locator("xpath=./div").first.click()
                    page.wait_for_timeout(500)

                sub_items = sub_ul.locator("xpath=./li").all()
                for sub in sub_items:
                    process_menu(sub, f"{full_text} > ")
            else:
                try:
                    click_target = title_span if title_span.count() > 0 else menu_item.locator("xpath=./div").first
                    click_target.click()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(1000)

                    page_texts = collect_page_texts(page)
                    for pt in page_texts:
                        collected_texts.add(pt)
                        print(f"    📄 页面文本: {pt}")
                except Exception as e:
                    print(f"    ⚠️ 点击叶子菜单失败: {e}")
        except Exception as e:
            print(f"  ⚠️ 处理菜单项出错: {e}")

    for i in range(1, 7):
        menu_item = page.locator(f"xpath={menu_xpath_base.replace('{i}', str(i))}")
        if menu_item.count() > 0:
            process_menu(menu_item)

    return list(collected_texts)


def switch_language(page, target_lang="EN", lang_btn_xpath="//*[@id='app']/section/header/div/a"):
    """
    切换到指定语言
    
    Args:
        page: Playwright Page 对象
        target_lang: 目标语言，"EN" 或 "CN"，默认 "EN"
        lang_btn_xpath: 语言切换按钮的 XPath，默认为 J&T 系统的按钮路径
    """
    lang_btn = page.locator(f"xpath={lang_btn_xpath}").first
    lang_btn.click()
    page.wait_for_timeout(500)

    if target_lang == "EN":
        lang_option = page.locator("xpath=/html/body/div[2]/div/div/div/ul/li[2]/span").first
    else:
        lang_option = page.locator("xpath=/html/body/div[2]/div/div/div/ul/li[1]/span").first
    
    lang_option.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)


def find_untranslated_elements(page, chinese_texts):
    """
    遍历页面所有元素，找出文本内容与 chinese_texts 中任一完全相同的元素
    
    Args:
        page: Playwright Page 对象
        chinese_texts: 中文文本列表或集合
    
    Returns:
        list: 匹配的元素列表，每个元素为 (element, matched_text) 元组
    """
    matched = []
    elements = page.locator("body *").all()
    print(f"🔍 扫描页面中所有元素（共 {len(elements)} 个）")

    for el in elements:
        try:
            if not el.is_visible():
                continue
            text = safe_text(el.inner_text())
            if not text:
                continue
            if text in chinese_texts:
                matched.append((el, text))
                print(f"  ⚠️ 发现未翻译文本: '{text}'")
        except:
            pass

    return matched


def highlight_and_screenshot(page, element, text, index, save_dir="C:\\doc"):
    """
    高亮元素（红色边框）并截图整个窗口
    
    Args:
        page: Playwright Page 对象
        element: 要高亮的 Playwright Locator 对象
        text: 元素的文本内容（用于生成文件名）
        index: 序号（用于生成文件名）
        save_dir: 截图保存目录，默认 "C:\\doc"
    
    Returns:
        bool: 截图成功返回 True，失败返回 False
    """
    original_border = None
    try:
        original_border = element.evaluate("el => el.style.border")
        element.evaluate("el => { el.style.border = '3px solid red'; }")

        os.makedirs(save_dir, exist_ok=True)

        safe_name = text.replace("\\", "_").replace("/", "_").replace(":", "_") \
                      .replace("*", "_").replace("?", "_").replace("\"", "_") \
                      .replace("<", "_").replace(">", "_").replace("|", "_")
        filename = f"{index:03d}_{safe_name}.png"
        filepath = os.path.join(save_dir, filename)

        element.scroll_into_view_if_needed()
        page.wait_for_timeout(200)

        page.screenshot(path=filepath, full_page=False)
        print(f"  📸 截图已保存: {filepath}")

        return True
    except Exception as e:
        print(f"  ❌ 高亮/截图失败: {e}")
        return False
    finally:
        if original_border is not None:
            try:
                element.evaluate("(el, border) => { el.style.border = border; }", original_border)
            except Exception:
                pass


def wait_for_element_visible(page, selector, timeout=10000):
    """
    等待元素可见
    
    Args:
        page: Playwright Page 对象
        selector: 元素选择器
        timeout: 超时时间（毫秒），默认 10000
    
    Returns:
        bool: 元素可见返回 True，超时返回 False
    """
    try:
        element = page.locator(selector).first
        element.wait_for(state="visible", timeout=timeout)
        return True
    except:
        return False


def wait_for_page_load(page, timeout=10000):
    """
    等待页面加载完成
    
    Args:
        page: Playwright Page 对象
        timeout: 超时时间（毫秒），默认 10000
    
    Returns:
        bool: 页面加载完成返回 True，超时返回 False
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
        return True
    except:
        return False


def take_screenshot(page, filename, full_page=False):
    """
    截取页面截图
    
    Args:
        page: Playwright Page 对象
        filename: 截图文件名
        full_page: 是否截全页，默认 False（仅截视口）
    
    Returns:
        bool: 截图成功返回 True，失败返回 False
    """
    try:
        page.screenshot(path=filename, full_page=full_page)
        print(f"📸 截图已保存: {filename}")
        return True
    except Exception as e:
        print(f"❌ 截图失败: {e}")
        return False


def click_element(page, selector, timeout=10000):
    """
    点击元素
    
    Args:
        page: Playwright Page 对象
        selector: 元素选择选择器
        timeout: 等待超时时间（毫秒），默认 10000
    
    Returns:
        bool: 点击成功返回 True，失败返回 False
    """
    try:
        element = page.locator(selector).first
        element.wait_for(state="visible", timeout=timeout)
        element.click()
        return True
    except Exception as e:
        print(f"❌ 点击元素失败: {e}")
        return False


def fill_input(page, selector, value, timeout=10000):
    """
    填充输入框
    
    Args:
        page: Playwright Page 对象
        selector: 元素选择器
        value: 要填充的值
        timeout: 等待超时时间（毫秒），默认 10000
    
    Returns:
        bool: 填充成功返回 True，失败返回 False
    """
    try:
        element = page.locator(selector).first
        element.wait_for(state="visible", timeout=timeout)
        element.fill(value)
        return True
    except Exception as e:
        print(f"❌ 填充输入框失败: {e}")
        return False


def get_element_text(page, selector, timeout=10000):
    """
    获取元素文本
    
    Args:
        page: Playwright Page 对象
        selector: 元素选择器
        timeout: 等待超时时间（毫秒），默认 10000
    
    Returns:
        str: 元素文本，失败返回空字符串
    """
    try:
        element = page.locator(selector).first
        element.wait_for(state="visible", timeout=timeout)
        return safe_text(element.inner_text())
    except Exception as e:
        print(f"❌ 获取元素文本失败: {e}")
        return ""


def check_element_exists(page, selector, timeout=5000):
    """
    检查元素是否存在
    
    Args:
        page: Playwright Page 对象
        selector: 元素选择器
        timeout: 等待超时时间（毫秒），默认 5000
    
    Returns:
        bool: 元素存在返回 True，否则返回 False
    """
    try:
        element = page.locator(selector).first
        element.wait_for(state="attached", timeout=timeout)
        return True
    except:
        return False
