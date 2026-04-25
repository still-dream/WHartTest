"""
公共模块使用示例

展示如何使用 slider_captcha 和 page_utils 模块进行 UI 自动化。
"""

from playwright.sync_api import sync_playwright
from slider_captcha import handle_slider_captcha
from page_utils import (
    fill_input,
    click_element,
    wait_for_element_visible,
    take_screenshot,
    get_element_text
)


def example_1_simple_login():
    """
    示例 1：简单的登录流程
    """
    print("\n" + "="*50)
    print("示例 1：简单的登录流程")
    print("="*50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            page.goto("https://demo-home-admin.jtexpress.ph/login")
            
            fill_input(page, 'input[name="username"]', "testuser")
            fill_input(page, 'input[name="password"]', "password123")
            
            take_screenshot(page, "example1_before_login.png")
            
            click_element(page, 'button[type="submit"]')
            
            handle_slider_captcha(page)
            
            take_screenshot(page, "example1_after_login.png")
            print("✅ 登录成功！")
            
        except Exception as e:
            print(f"❌ 登录失败: {e}")
        finally:
            browser.close()


def example_2_form_submission():
    """
    示例 2：表单提交
    """
    print("\n" + "="*50)
    print("示例 2：表单提交")
    print("="*50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            page.goto("https://example.com/form")
            
            fill_input(page, "#name", "张三")
            fill_input(page, "#email", "zhangsan@example.com")
            fill_input(page, "#phone", "13800138000")
            
            take_screenshot(page, "example2_before_submit.png")
            
            click_element(page, "#submit-button")
            
            if wait_for_element_visible(page, ".success-message", timeout=5000):
                success_text = get_element_text(page, ".success-message")
                print(f"✅ 提交成功: {success_text}")
            else:
                print("❌ 提交失败或超时")
                
            take_screenshot(page, "example2_after_submit.png")
            
        except Exception as e:
            print(f"❌ 表单提交失败: {e}")
        finally:
            browser.close()


def example_3_navigation_and_screenshot():
    """
    示例 3：页面导航和截图
    """
    print("\n" + "="*50)
    print("示例 3：页面导航和截图")
    print("="*50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            urls = [
                "https://example.com",
                "https://example.com/about",
                "https://example.com/contact"
            ]
            
            for idx, url in enumerate(urls, start=1):
                page.goto(url)
                take_screenshot(page, f"example3_page_{idx}.png")
                print(f"✅ 已访问并截图: {url}")
                
        except Exception as e:
            print(f"❌ 导航失败: {e}")
        finally:
            browser.close()


def example_4_element_interaction():
    """
    示例 4：元素交互
    """
    print("\n" + "="*50)
    print("示例 4：元素交互")
    print("="*50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            page.goto("https://example.com")
            
            if wait_for_element_visible(page, "#dropdown", timeout=5000):
                click_element(page, "#dropdown")
                print("✅ 点击下拉菜单")
                
                if wait_for_element_visible(page, ".dropdown-item", timeout=2000):
                    item_text = get_element_text(page, ".dropdown-item")
                    print(f"✅ 获取到菜单项: {item_text}")
            
            take_screenshot(page, "example4_interaction.png")
            
        except Exception as e:
            print(f"❌ 元素交互失败: {e}")
        finally:
            browser.close()


def example_5_custom_captcha():
    """
    示例 5：自定义滑块验证
    """
    print("\n" + "="*50)
    print("示例 5：自定义滑块验证")
    print("="*50)
    
    from slider_captcha import human_like_slider
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            page.goto("https://example.com/login")
            
            fill_input(page, "#username", "testuser")
            fill_input(page, "#password", "password123")
            click_element(page, "#login-button")
            
            success = human_like_slider(
                page,
                verify_box_selector=".custom-captcha-box",
                slider_block_selector=".custom-slider",
                refresh_btn_selector=".custom-refresh",
                bg_selector=".custom-bg",
                gap_selector=".custom-gap",
                max_retries=10
            )
            
            if success:
                print("✅ 自定义滑块验证成功！")
            else:
                print("❌ 自定义滑块验证失败")
                
            take_screenshot(page, "example5_captcha.png")
            
        except Exception as e:
            print(f"❌ 自定义验证失败: {e}")
        finally:
            browser.close()


def main():
    """
    主函数：运行所有示例
    """
    print("\n" + "="*50)
    print("UI 自动化公共模块使用示例")
    print("="*50)
    
    examples = [
        ("简单的登录流程", example_1_simple_login),
        ("表单提交", example_2_form_submission),
        ("页面导航和截图", example_3_navigation_and_screenshot),
        ("元素交互", example_4_element_interaction),
        ("自定义滑块验证", example_5_custom_captcha)
    ]
    
    print("\n可用示例：")
    for idx, (name, _) in enumerate(examples, start=1):
        print(f"  {idx}. {name}")
    
    print("\n请选择要运行的示例（1-5），或输入 'all' 运行所有示例：")
    choice = input("选择: ").strip()
    
    if choice.lower() == 'all':
        for name, func in examples:
            try:
                func()
            except Exception as e:
                print(f"❌ 示例 '{name}' 执行失败: {e}")
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        idx = int(choice) - 1
        name, func = examples[idx]
        try:
            func()
        except Exception as e:
            print(f"❌ 示例 '{name}' 执行失败: {e}")
    else:
        print("❌ 无效的选择")


if __name__ == "__main__":
    main()
