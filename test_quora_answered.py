from playwright.sync_api import sync_playwright
import time

def get_chrome_debugging_port():
    """Get the debugging port of running Chrome instance"""
    try:
        import requests
        response = requests.get('http://localhost:9222/json/version')
        if response.status_code == 200:
            print("✓ Found running Chrome instance")
            return 9222
            
        print("\n⚠️  Please start Chrome with debugging enabled first:")
        print("/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        return None
        
    except requests.exceptions.ConnectionError:
        print("\n⚠️  Please start Chrome with debugging enabled first:")
        print("/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        return None

def check_if_already_answered(page):
    """Check if we've already answered this question"""
    try:
        print("Checking for existing answers...")
        
        # Look for answers by our username
        has_answer = page.evaluate('''() => {
            const answers = document.querySelectorAll('.q-box.qu-pt--medium');
            console.log('Found answers:', answers.length);
            
            const results = Array.from(answers).map(answer => {
                const authorElement = answer.querySelector('a[class*="user"]');
                const authorName = authorElement?.textContent;
                console.log('Author found:', authorName);
                return authorName;
            });
            
            console.log('All authors:', results);
            return results.some(name => name?.includes('Facet'));
        }''')
        
        print(f"Has answer: {has_answer}")
        return has_answer
        
    except Exception as e:
        print(f"Error checking for existing answers: {str(e)}")
        return True  # Safer to assume we've answered if we can't check

def main():
    test_url = "https://www.quora.com/What-are-some-SEO-automation-tools-that-use-AI"
    
    debugging_port = get_chrome_debugging_port()
    if not debugging_port:
        return
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{debugging_port}")
            context = browser.contexts[0]
            page = context.new_page()
            
            print(f"\nVisiting test URL: {test_url}")
            page.goto(test_url)
            time.sleep(5)
            
            print("\nTesting already_answered check...")
            has_answer = check_if_already_answered(page)
            
            print("\nResults:")
            print(f"Has existing answer: {has_answer}")
            
            # Let's also try some alternative selectors
            print("\nTrying alternative selectors...")
            
            alternative_selectors = [
                '.q-box.spacing_log_answer_content',
                '.q-text.qu-dynamicFontSize--regular',
                '.q-box.qu-borderBottom'
            ]
            
            for selector in alternative_selectors:
                try:
                    elements = page.query_selector_all(selector)
                    print(f"\nSelector '{selector}':")
                    print(f"Found {len(elements)} elements")
                    
                    # Try to find author names with this selector
                    authors = page.evaluate(f'''() => {{
                        const elements = document.querySelectorAll('{selector}');
                        return Array.from(elements).map(el => {{
                            const authorEl = el.querySelector('a[class*="user"]');
                            return authorEl ? authorEl.textContent : null;
                        }}).filter(Boolean);
                    }}''')
                    
                    print("Authors found:", authors)
                    
                except Exception as e:
                    print(f"Error with selector {selector}: {str(e)}")
            
            input("\nPress Enter to exit...")
            
        except Exception as e:
            print(f"Fatal error: {str(e)}")
        finally:
            if 'page' in locals():
                page.close()
            if 'browser' in locals():
                browser.disconnect()

if __name__ == "__main__":
    main() 