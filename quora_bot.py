from playwright.async_api import async_playwright
import os
import time
import random
import openai
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")
openai.api_key = OPENAI_API_KEY

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

def get_search_queries():
    """Return a list of search queries to target Quora content"""
    queries = [
        # SEO and Marketing Questions
        'site:quora.com "keyword research tools"',
        'site:quora.com "SEO strategy" after:2023',
        'site:quora.com "content marketing tips"',
        'site:quora.com "digital marketing advice"',
        
        # Tool-Related Questions
        'site:quora.com "best SEO tools"',
        'site:quora.com "keyword research software"',
        'site:quora.com "SEO automation tools"',
        'site:quora.com "content optimization tools"',
        
        # Strategy Questions
        'site:quora.com "how to find keywords"',
        'site:quora.com "keyword research strategy"',
        'site:quora.com "SEO keyword tips"',
        'site:quora.com "content strategy help"',
        
        # Problem-Solving Questions
        'site:quora.com "keyword research problems"',
        'site:quora.com "SEO challenges"',
        'site:quora.com "content optimization issues"',
        'site:quora.com "keyword difficulty"'
    ]
    
    random.shuffle(queries)
    return queries

def generate_comment(post_info):
    """Generate a contextual comment using ChatGPT"""
    try:
        prompt = f"""You are a digital marketer who uses kwrds.ai and is answering a Quora question. Generate a helpful, detailed answer as a satisfied user.

Question/Context:
{post_info['content']}

Guidelines:
- Write as a genuine user/customer of kwrds.ai, not an employee
- Be detailed and helpful
- Include specific examples or steps when relevant
- Keep it professional but conversational
- Mention kwrds.ai naturally as a tool you use
- Frame kwrds.ai as a helpful tool you've discovered
- Focus on providing value first, then mention the tool
- Keep under 4-5 paragraphs
- Don't use quotation marks
- Use single newlines between paragraphs (not double)

Example good answers:
Based on my experience, the key to effective keyword research is combining multiple data sources. I've been using kwrds.ai for this lately, and it's helped me identify opportunities I was missing before. Here's what I recommend...

What's worked well for me is...

Bad examples to avoid:
- "At kwrds.ai, we offer..." (sounds like an employee)
- "You should try kwrds.ai" (too promotional)
- Short, unhelpful answers

Generate a natural, helpful answer that includes kwrds.ai without quotation marks:"""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a digital marketer who uses kwrds.ai. Write as a satisfied user, not an employee."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        comment = response.choices[0].message.content.strip()
        
        # Clean up newlines to ensure single spacing between paragraphs
        comment = comment.replace('\n\n', '\n').replace('\n\n', '\n')
        
        if 'kwrds.ai' not in comment or any(phrase in comment.lower() for phrase in ['at kwrds.ai', 'our tool', 'we offer', 'we provide']):
            print("Comment needs revision (missing kwrds.ai or sounds like employee), regenerating...")
            return generate_comment(post_info)
            
        return comment
        
    except Exception as e:
        print(f"Error generating comment: {str(e)}")
        return None

def extract_quora_urls(page, html_content):
    """Extract Quora URLs from Google search results"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        urls = []
        for link in soup.select('div.g a'):
            href = str(link.get('href', ''))
            
            if not 'quora.com' in href:
                continue
                
            if '/url?q=' in href:
                href = href.split('/url?q=')[1].split('&')[0]
                
            if href.startswith(('http://', 'https://')):
                urls.append(href)
                
        return list(dict.fromkeys(urls))
        
    except Exception as e:
        print(f"Error extracting URLs: {str(e)}")
        return []

def check_if_already_answered(page):
    """Check if we've already answered this question"""
    try:
        # Look for answers by our username
        has_answer = page.evaluate('''() => {
            const answers = document.querySelectorAll('.q-box.qu-pt--medium');
            return Array.from(answers).some(answer => {
                const authorElement = answer.querySelector('a[class*="user"]');
                return authorElement?.textContent?.includes('Facet');
            });
        }''')
        
        return has_answer
        
    except Exception as e:
        print(f"Error checking for existing answers: {str(e)}")
        return True  # Safer to assume we've answered if we can't check

async def post_answer(page, answer):
    """Post an answer on Quora"""
    try:
        print("\nPosting answer...")
        
        # Click answer button - try both selectors
        answer_button_selectors = [
            'button[class*="q-click-wrapper"][class*="qu-active--textDecoration--none"]',
            'button:has-text("Answer")'
        ]
        
        for selector in answer_button_selectors:
            try:
                await page.click(selector)
                print(f"✓ Clicked answer button using selector: {selector}")
                break
            except Exception:
                continue
        else:
            print("✗ Could not find answer button with any selector")
            return False
            
        await page.wait_for_timeout(15000)
        print("Looking for editor...")
        
        # Find and fill answer box - try multiple selectors
        editor_selectors = [
            'div[data-kind="doc"][contenteditable="true"]',
            'div.doc[contenteditable="true"]',
            'div.q-box div[contenteditable="true"]',
            'div[role="textbox"]',
            'div.notranslate.public-DraftEditor-content'
        ]
        
        # Debug: Print all contenteditable elements
        await page.evaluate('''() => {
            const elements = document.querySelectorAll('[contenteditable="true"]');
            console.log('Found contenteditable elements:', elements.length);
            elements.forEach(el => {
                console.log('Element:', el.tagName, 'Classes:', el.className, 'Data-kind:', el.getAttribute('data-kind'));
            });
        }''')
        
        # Try each editor selector
        for editor_selector in editor_selectors:
            try:
                print(f"\nTrying selector: {editor_selector}")
                
                # First check if element exists
                element = await page.query_selector(editor_selector)
                if not element:
                    print(f"Element not found with selector: {editor_selector}")
                    continue
                    
                print(f"Found element with selector: {editor_selector}")
                
                # Try to focus and clear the element
                await page.focus(editor_selector)
                await page.wait_for_timeout(2000)
                
                # Split the answer where "kwrds.ai" appears
                parts = answer.split("kwrds.ai")
                
                async def type_with_retry(text, selector, max_retries=3):
                    for attempt in range(max_retries):
                        try:
                            # Type in smaller chunks
                            chunk_size = 50
                            for i in range(0, len(text), chunk_size):
                                chunk = text[i:i + chunk_size]
                                await page.type(selector, chunk, delay=50)
                                await page.wait_for_timeout(500)
                            return True
                        except Exception as e:
                            print(f"Typing attempt {attempt + 1} failed: {str(e)}")
                            if attempt == max_retries - 1:
                                raise
                            await page.wait_for_timeout(1000)
                
                # Type each part with retries
                for i, part in enumerate(parts):
                    if i > 0:
                        await page.type(editor_selector, "kwrds.ai", delay=100)
                        await page.wait_for_timeout(2000)
                        await page.type(editor_selector, " ", delay=100)
                        await page.wait_for_timeout(1000)
                    
                    await type_with_retry(part, editor_selector)
                
                print(f"✓ Typed answer using selector: {editor_selector}")
                break
            except Exception as e:
                print(f"Failed with selector {editor_selector}: {str(e)}")
                continue
        else:
            print("✗ Could not find answer box with any selector")
            return False
            
        await page.wait_for_timeout(12000)
        
        print("Will post in 60 seconds...")
        await page.wait_for_timeout(60000)
        
        # Click post button - try multiple selectors
        try:
            post_button_selectors = [
                'button.q-click-wrapper.puppeteer_test_modal_submit',
                'button.q-click-wrapper[class*="puppeteer_test_modal_submit"]',
                'button.puppeteer_test_modal_submit',
                'button[class*="qu-bg--blue"] div.puppeteer_test_button_text',
                'button:has-text("Post")',
                'button[class*="submit_button"]'
            ]
            
            for selector in post_button_selectors:
                try:
                    print(f"Trying post button selector: {selector}")
                    element = await page.query_selector(selector)
                    if element:
                        await page.click(selector)
                        print(f"✓ Clicked post button using selector: {selector}")
                        return True
                except Exception as e:
                    print(f"Failed with post button selector {selector}: {str(e)}")
                    continue
            
            print("✗ Could not find post button with any selector")
            return False
            
        except Exception as e:
            print(f"Error clicking post button: {str(e)}")
            return False
            
    except Exception as e:
        print(f"Error posting answer: {str(e)}")
        return False

async def main():
    debugging_port = get_chrome_debugging_port()
    if not debugging_port:
        return
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{debugging_port}")
            context = browser.contexts[0]
            page = await context.new_page()
            
            queries = get_search_queries()
            
            for query_index, query in enumerate(queries, 1):
                print(f"\n=== Processing Query {query_index}/{len(queries)} ===")
                print(f"Query: {query}")
                
                await page.goto('https://www.google.com')
                search_box = page.locator('textarea[name="q"]')
                await search_box.fill(query)
                await search_box.press('Enter')
                await page.wait_for_timeout(5000)
                
                urls = extract_quora_urls(page, await page.content())
                print(f"\nFound {len(urls)} Quora URLs:")
                for i, url in enumerate(urls, 1):
                    print(f"{i}. {url}")
                
                for url in urls:
                    try:
                        print(f"\nProcessing: {url}")
                        await page.goto(url)
                        await page.wait_for_timeout(15000)
                        
                        if await check_if_already_answered(page):
                            print("Already answered this question, skipping...")
                            continue
                        
                        question = await page.evaluate('() => document.querySelector(".q-box.qu-userSelect--text").innerText')
                        if not question:
                            selector = input("Enter alternative selector: ")
                            question = await page.evaluate(f'() => document.querySelector("{selector}").innerText')
                        
                        print(f"\nQuestion: {question[:200]}...")
                        
                        post_info = {
                            'url': url,
                            'content': question
                        }
                        
                        answer = generate_comment(post_info)
                        if not answer:
                            continue
                        
                        print(f"\nGenerated answer: {answer[:200]}...")
                        
                        success = await post_answer(page, answer)
                        if success:
                            print("✓ Successfully posted answer!")
                        
                        delay = random.randint(60, 120)
                        print(f"\nWaiting {delay} seconds before next URL...")
                        await page.wait_for_timeout(delay)
                        
                    except Exception as e:
                        print(f"Error processing URL: {str(e)}")
                        continue
                
                delay = random.randint(120, 180)
                print(f"\nWaiting {delay} seconds before next query...")
                await page.wait_for_timeout(delay * 1000)
                
        except Exception as e:
            print(f"Fatal error: {str(e)}")
            input("Press Enter to exit...")
        finally:
            if 'page' in locals():
                await page.close()
            if 'browser' in locals():
                await browser.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 