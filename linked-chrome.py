from playwright.sync_api import sync_playwright
import os
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import time
import random
import subprocess
import json
import openai
from dotenv import load_dotenv

load_dotenv()

"""
Need to run chrome with:

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

"""

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")
openai.api_key = OPENAI_API_KEY

def get_chrome_debugging_port():
    """Get the debugging port of running Chrome instance"""
    try:
        # Check if Chrome is already running with debugging port
        response = requests.get('http://localhost:9222/json/version')
        if response.status_code == 200:
            print("✓ Found running Chrome instance")
            return 9222
            
        # If not running with debugging, print instructions
        print("\n⚠️  Please start Chrome with debugging enabled first:")
        print("1. Close all Chrome instances")
        print("2. Run this command in terminal:")
        print("/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        print("3. Then run this script again")
        return None
        
    except requests.exceptions.ConnectionError:
        print("\n⚠️  Please start Chrome with debugging enabled first:")
        print("1. Close all Chrome instances")
        print("2. Run this command in terminal:")
        print("/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        print("3. Then run this script again")
        return None

def get_search_queries():
    """Return a list of search queries to target LinkedIn content"""
    
    queries = [
        # LinkedIn Groups and Discussions
        'site:linkedin.com "SEO discussion"',
        'site:linkedin.com "digital marketing trends"',
        'site:linkedin.com "content strategy"',
        'site:linkedin.com "keyword research tips"',
        
        # LinkedIn Posts by Topic
        'site:linkedin.com "SEO strategy" after:2023',
        'site:linkedin.com "content marketing" after:2023',
        'site:linkedin.com "keyword research" after:2023',
        'site:linkedin.com "digital marketing tips" after:2023',
        
        # Viral/Trending Content
        'site:linkedin.com "went viral" after:2023',
        'site:linkedin.com "trending topic" after:2023',
        'site:linkedin.com "breaking news" after:2023',
        'site:linkedin.com "hit 1 million" after:2023',
        
        # Industry Leaders and Influencers
        'site:linkedin.com "thought leadership" SEO',
        'site:linkedin.com "industry insights" marketing',
        'site:linkedin.com "expert opinion" digital',
        'site:linkedin.com "marketing strategy" influencer',
        
        # AI and Tech Trends
        'site:linkedin.com "AI in marketing" after:2023',
        'site:linkedin.com "ChatGPT for business" after:2023',
        'site:linkedin.com "AI tools" marketing after:2023',
        'site:linkedin.com "machine learning" SEO after:2023',
        
        # Growth and Success Stories
        'site:linkedin.com "success story" marketing',
        'site:linkedin.com "case study" SEO results',
        'site:linkedin.com "growth strategy" worked',
        'site:linkedin.com "marketing success" how',
        
        # Tips and Tutorials
        'site:linkedin.com "SEO tips" guide',
        'site:linkedin.com "marketing tutorial" how',
        'site:linkedin.com "step by step" SEO',
        'site:linkedin.com "quick tip" marketing',
        
        # Industry Updates
        'site:linkedin.com "Google update" SEO',
        'site:linkedin.com "algorithm change" impact',
        'site:linkedin.com "new feature" marketing',
        'site:linkedin.com "industry news" digital',
        
        # Tools and Software
        'site:linkedin.com "best tools" SEO',
        'site:linkedin.com "software review" marketing',
        'site:linkedin.com "tool comparison" SEO',
        'site:linkedin.com "recommended tools" digital',
        
        # Questions and Engagement
        'site:linkedin.com "what do you think" SEO',
        'site:linkedin.com "asking for advice" marketing',
        'site:linkedin.com "need recommendations" tools',
        'site:linkedin.com "your opinion" strategy',
        
        # LinkedIn Pulse Articles
        'site:linkedin.com/pulse "SEO strategies"',
        'site:linkedin.com/pulse "content marketing" after:2023',
        'site:linkedin.com/pulse "digital marketing" after:2023',
        'site:linkedin.com/pulse "marketing automation"',
        'site:linkedin.com/pulse "AI in marketing"',
        'site:linkedin.com/pulse "SEO tools"',
        'site:linkedin.com/pulse "content strategy"',
        'site:linkedin.com/pulse "marketing trends"',
        
        # Combined Searches
        'site:linkedin.com/pulse OR site:linkedin.com/posts "SEO tips"',
        'site:linkedin.com/pulse OR site:linkedin.com/posts "marketing strategy" after:2023',
        'site:linkedin.com/pulse OR site:linkedin.com/posts "AI tools" after:2023',
        'site:linkedin.com/pulse OR site:linkedin.com/posts "content optimization"'
    ]
    
    # Shuffle the queries randomly
    random.shuffle(queries)
    
    return queries

def get_random_proxy():
    """Get a random proxy from the list"""
    prox_list = [
        'geo.iproyal.com:12321:raVWrZ8duQaStI6t:r79i2q51TaQHYmy1_country-us',
        'us.smartproxy.com:10000:sprkucstlr:gd3patxyW6Dln73YpG',
        'pr.oxylabs.io:7777:kwrds_ai_mk:fLeYms_pd_d6PA2'
    ]
    proxy = random.choice(prox_list)
    host, port, user, password = proxy.split(':')
    return {
        'http': f'http://{user}:{password}@{host}:{port}',
        'https': f'http://{user}:{password}@{host}:{port}'
    }

def search_google_for_posts(page, query):
    """Step 1: Search Google for LinkedIn posts using Playwright"""
    print(f"\nStep 1: Searching Google for: {query}")
    
    try:
        # Go to Google first
        page.goto('https://www.google.com')
        print("✓ Navigated to Google")
        
        # Wait for and fill search box
        search_box = page.locator('textarea[name="q"]')
        search_box.fill(query)
        search_box.press('Enter')
        
        print("✓ Submitted search query")
        time.sleep(5)
        # while input("Type 'y' when search results have loaded: ").lower() != 'y':
        #     print("Please type 'y' when ready...")
        
        # Get the page content
        html_content = page.content()
        print("✓ Retrieved search results")
        
        return html_content
            
    except Exception as e:
        print(f"✗ Error in Google search: {str(e)}")
        return None

def extract_linkedin_urls(html_content):
    """Step 2: Extract LinkedIn URLs from Google search results"""
    print("\nStep 2: Extracting LinkedIn URLs")
    
    urls = []
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look specifically for search result links
        for link in soup.select('div.g a'):
            href = str(link.get('href', ''))
            
            # Skip if not a LinkedIn URL
            if not any(x in href for x in ['linkedin.com/posts', 'linkedin.com/feed/update', 'linkedin.com/pulse']):
                continue
                
            print(f"\nFound potential LinkedIn URL: {href}")
            
            try:
                # Clean the URL
                if '/url?q=' in href:
                    clean_url = href.split('/url?q=')[1].split('&')[0]
                else:
                    clean_url = href
                
                # Ensure URL starts with http/https
                if not clean_url.startswith(('http://', 'https://')):
                    clean_url = 'https://' + clean_url.lstrip('/')
                
                # URL decode
                clean_url = requests.utils.unquote(clean_url)
                
                # Validate URL format and structure
                if (clean_url.startswith(('http://', 'https://')) and 
                    any(x in clean_url for x in ['linkedin.com/posts', 'linkedin.com/feed/update', 'linkedin.com/pulse']) and
                    len(clean_url) > 30):  # Basic length check
                    
                    # Remove any tracking parameters
                    if '?' in clean_url:
                        clean_url = clean_url.split('?')[0]
                    
                    urls.append(clean_url)
                    print(f"✓ Added valid URL: {clean_url}")
            except Exception as e:
                print(f"✗ Error cleaning URL {href}: {str(e)}")
                continue
        
        # Remove duplicates while preserving order
        urls = list(dict.fromkeys(urls))
        
        print(f"\n✓ Found {len(urls)} valid LinkedIn URLs:")
        for i, url in enumerate(urls, 1):
            print(f"{i}. {url}")
        
        return urls
        
    except Exception as e:
        print(f"✗ Error extracting URLs: {str(e)}")
        return []

def visit_linkedin_post(page, url):
    """Step 3: Visit LinkedIn post and extract content"""
    print(f"\nStep 3: Attempting to visit LinkedIn post: {url}")
    
    try:
        # Validate URL before visiting
        if not url.startswith(('http://', 'https://')):
            print("✗ Invalid URL format, skipping...")
            return None
            
        print(f"About to visit: {url}")
        time.sleep(5)
        
        try:
            # Visit the URL with a timeout
            with page.expect_navigation(timeout=10000) as navigation_info:
                page.goto(url)
                navigation_info.value
        except Exception as nav_error:
            print(f"✗ Navigation failed: {str(nav_error)}")
            print("Skipping this URL...")
            return None
            
        # Check if we landed on a valid page
        current_url = page.url
        if 'linkedin.com/login' in current_url or 'linkedin.com/checkpoint' in current_url:
            print("✗ Redirected to login page, skipping...")
            return None
            
        print("✓ Navigated to post")
        time.sleep(8)
        # response = input("Type 'y' if page loaded successfully, 's' to skip: ").lower()
        # if response == 's':
        #     print("Skipping this URL...")
        #     return None
        # elif response != 'y':
        #     print("Invalid input, skipping...")
        #     return None
        
        try:
            # First try to get post content with multiple possible selectors
            post_content = page.evaluate('''() => {
                // Array of possible content selectors
                const selectors = [
                    '.feed-shared-update-v2__description',
                    '.feed-shared-inline-show-more-text',
                    '.feed-shared-text-view',
                    '.feed-shared-update-v2__description feed-shared-inline-show-more-text--minimal-padding',
                    '.feed-shared-inline-show-more-text--3-lines',
                    '.feed-shared-inline-show-more-text--expanded'
                ];
                
                // Try each selector
                for (const selector of selectors) {
                    const element = document.querySelector(selector);
                    if (element && element.innerText.trim()) {
                        return element.innerText.trim();
                    }
                }
                
                // If no specific selector works, try to find any post content
                const possibleContent = document.querySelector('article');
                if (possibleContent) {
                    return possibleContent.innerText.trim();
                }
                
                return null;
            }''')
            
            if not post_content:
                print("✗ Could not find post content, trying alternative method...")
                # Try to get any text content as fallback
                post_content = page.evaluate('''() => {
                    const article = document.querySelector('article');
                    if (!article) return null;
                    
                    // Remove any unwanted elements
                    const textContent = Array.from(article.querySelectorAll('p, span, div'))
                        .map(el => el.innerText)
                        .filter(text => text.trim())
                        .join('\n');
                    
                    return textContent || null;
                }''')
            
            if not post_content:
                print("✗ Could not find any post content, skipping...")
                return None
            
            # Clean up the content
            post_content = post_content.strip()
            if len(post_content) < 10:  # Minimum content length check
                print("✗ Post content too short, skipping...")
                return None
            
            # Extract post details
            post_info = {
                'url': url,
                'content': post_content,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            print("✓ Successfully extracted post content")
            print(f"Content preview: {post_content[:200]}...")
            
            time.sleep(5)
            # response = input("Type 'y' if the content looks correct, 's' to skip: ").lower()
            # if response == 's':
            #     return None
            # elif response != 'y':
            #     print("Invalid input, skipping...")
            #     return None
                
            return post_info
            
        except Exception as e:
            print(f"✗ Error extracting content: {str(e)}")
            return None
            
    except Exception as e:
        print(f"✗ Error visiting post: {str(e)}")
        return None

def generate_comment(post_info):
    """Generate a contextual comment using ChatGPT"""
    try:
        prompt = f"""You are a digital marketer who uses kwrds.ai and is engaging with a LinkedIn post. Generate a thoughtful comment as a satisfied user.

Post Content:
{post_info['content']}

Guidelines:
- Write as a genuine user/customer of kwrds.ai, not an employee
- Keep it professional but conversational
- Be specific to the post content
- Add value to the discussion
- Keep it under 2-3 sentences
- Be positive and supportive
- Don't use any quotation marks
- Mention kwrds.ai naturally as a tool you use
- Frame kwrds.ai as a helpful tool you've discovered and use

Example good comments:
Great insights! I've been using kwrds.ai for my content strategy lately and seeing similar results with optimization.
This resonates with my experience - since discovering kwrds.ai, I've been able to streamline my keyword research process significantly.
Valuable perspective on content marketing. I've found kwrds.ai particularly helpful for implementing these kinds of strategies.

Bad examples to avoid:
- "At kwrds.ai, we've seen..." (sounds like an employee)
- "Our tool kwrds.ai..." (implies ownership)
- "kwrds.ai can help you..." (sounds promotional)

Generate a natural comment as a user that includes kwrds.ai without quotation marks:"""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a digital marketer who uses kwrds.ai. Write as a satisfied user, not an employee. Never use quotation marks."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        comment = response.choices[0].message.content.strip().replace('"', '').replace('"', '').replace('"', '')
        
        # Verify kwrds.ai is in the comment and doesn't sound like an employee
        if 'kwrds.ai' not in comment or any(phrase in comment.lower() for phrase in ['at kwrds.ai', 'our tool', 'we offer', 'we provide']):
            print("Comment needs revision (missing kwrds.ai or sounds like employee), regenerating...")
            return generate_comment(post_info)
            
        return comment
        
    except Exception as e:
        print(f"✗ Error generating comment: {str(e)}")
        return None

def prepare_comment(post_info):
    """Step 4: Prepare comment based on post content"""
    print("\nStep 4: Preparing comment")
    
    # Generate initial comment
    comment = generate_comment(post_info)
    if not comment:
        return None
        
    print(f"✓ Generated initial comment: {comment}")
    
    # Allow for regeneration
    while True:
        choice = input("\nUse this comment? (y)es, (r)egenerate, (m)anual, (s)kip: ").lower()
        
        if choice == 'y':
            return comment
        elif choice == 'r':
            print("\nRegenerating comment...")
            comment = generate_comment(post_info)
            if comment:
                print(f"✓ New comment: {comment}")
            else:
                print("✗ Failed to regenerate comment")
                return None
        elif choice == 'm':
            manual_comment = input("\nEnter your comment manually: ").strip()
            if manual_comment:
                return manual_comment
            print("Comment cannot be empty. Try again.")
        elif choice == 's':
            return None
        else:
            print("Invalid choice. Try again.")

def confirm_comment(post_info, comment):
    """Ask for confirmation before posting a comment"""
    return True, comment
    # print("\n=== Comment Confirmation ===")
    # print(f"Post URL: {post_info['url']}")
    # print(f"Post Content Preview: {post_info['content'][:200]}...")
    # print(f"\nProposed Comment: {comment}")
    # print("\nOptions:")
    # print("'y' - Post comment")
    # print("'e' - Edit comment")
    # print("'s' - Skip this post")
    # print("'q' - Quit program")
    
    # while True:
    #     choice = input("\nYour choice (y/e/s/q): ").lower()
        
    #     if choice == 'y':
    #         return True, comment
    #     elif choice == 'e':
    #         new_comment = input("\nEnter new comment: ")
    #         if new_comment.strip():
    #             return True, new_comment
    #         print("Comment cannot be empty. Please try again.")
    #     elif choice == 's':
    #         return False, None
    #     elif choice == 'q':
    #         raise SystemExit("Program terminated by user")
    #     else:
    #         print("Invalid choice. Please try again.")

def check_if_already_commented(page):
    """Check if Facet has already commented on this post"""
    print("\nChecking for existing Facet comments...")
    
    try:
        # Look for comments by Facet
        facet_comments = page.evaluate('''() => {
            const comments = document.querySelectorAll('.comments-comment-item__main-content');
            const facetComments = Array.from(comments).filter(comment => {
                const authorElement = comment.closest('article')?.querySelector('.comments-comment-meta__description-title');
                return authorElement?.textContent?.trim() === 'Facet';
            });
            return facetComments.length;
        }''')
        
        if facet_comments > 0:
            print(f"✗ Found {facet_comments} existing comment(s) by Facet")
            return True
        
        print("✓ No existing Facet comments found")
        return False
        
    except Exception as e:
        print(f"✗ Error checking for existing comments: {str(e)}")
        return True  # Fail safe - assume we've commented if we can't check

def post_comment(page, comment):
    """Step 5: Post comment on LinkedIn"""
    print("\nStep 5: Posting comment")
    
    try:
        # First check if we've already commented
        if check_if_already_commented(page):
            print("Skipping: Facet has already commented on this post")
            return False
        
        # Show what we're about to do
        print(f"About to post comment: {comment}")
        time.sleep(5)
        
        # Switch to Facet account first
        if not switch_to_facet_account(page):
            print("Failed to switch account, cancelling comment")
            return False
            
        # Find and click comment box
        print("Looking for comment box...")
        time.sleep(7)
        
        # Try different comment box selectors
        comment_box_selectors = [
            'div[data-placeholder="Add a comment…"]',
            'div[aria-placeholder="Add a comment…"]',
            'div.ql-editor[aria-placeholder="Add a comment…"]',
            'div.ql-editor[data-placeholder="Add a comment…"]',
            'div[role="textbox"][aria-placeholder="Add a comment…"]',
            'div[role="textbox"][data-placeholder="Add a comment…"]',
            'div.ql-editor[aria-label="Text editor for creating content"]',
            'div.comments-comment-box-comment__text-editor div[role="textbox"]'
        ]
        
        # Try each selector
        for selector in comment_box_selectors:
            try:
                page.click(selector)
                print(f"✓ Clicked comment box using selector: {selector}")
                break
            except Exception:
                continue
        else:
            print("✗ Could not find comment box")
            return False
        
        time.sleep(2)
        
        # Try different input selectors for typing
        input_selectors = [
            'div.ql-editor[contenteditable="true"]',
            'div[role="textbox"][contenteditable="true"]',
            'div.ql-editor[aria-label="Text editor for creating content"]',
            'div.comments-comment-box-comment__text-editor div[role="textbox"]'
        ]
        
        # Try each input selector
        for selector in input_selectors:
            try:
                page.fill(selector, comment)
                print(f"✓ Typed comment using selector: {selector}")
                break
            except Exception:
                continue
        else:
            print("✗ Could not find input box")
            return False
        
        print("✓ Typed comment")
        
        # Final confirmation
        response = input("Comment is ready. Type 'y' to post, or 'n' to cancel: ").lower()
        if response != 'y':
            print("Comment posting cancelled")
            return False
        
        # Try different post button selectors
        post_button_selectors = [
            'button.comments-comment-box__submit-button--cr',
            'button[aria-label="Post comment"]',
            'button.artdeco-button--primary:has-text("Post")',
            'form.comments-comment-box__form button[type="submit"]'
        ]
        
        # Try each post button selector
        for selector in post_button_selectors:
            try:
                page.click(selector)
                print(f"✓ Clicked post button using selector: {selector}")
                break
            except Exception:
                continue
        else:
            print("✗ Could not find post button")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error posting comment: {str(e)}")
        return None

def evaluate_comment(comment, post_info):
    """Evaluate if the comment is appropriate for the post"""
    try:
        evaluation_prompt = f"""Evaluate this LinkedIn comment for quality and appropriateness.

Post Content:
{post_info['content'][:500]}...

Proposed Comment:
{comment}

Evaluate:
1. Relevance to post (1-10)
2. Professionalism (1-10)
3. Naturalness (1-10)
4. Value added (1-10)
5. Risk level (1-10, lower is better)

Return evaluation in Python dict format:
{{
    "scores": {{
        "relevance": X,
        "professionalism": X,
        "naturalness": X,
        "value_added": X,
        "risk_level": X
    }},
    "should_revise": True/False,
    "reason": "explanation",
    "suggestions": "improvement ideas if needed"
}}"""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert at evaluating LinkedIn comment quality."},
                {"role": "user", "content": evaluation_prompt}
            ],
            temperature=0.7
        )

        # Parse the response
        evaluation = eval(response.choices[0].message.content.strip())
        
        # Print evaluation
        print("\nComment Evaluation:")
        for metric, score in evaluation['scores'].items():
            print(f"- {metric.replace('_', ' ').title()}: {score}/10")
        
        if evaluation['should_revise']:
            print(f"\nSuggested revision: {evaluation['reason']}")
            
        return evaluation
        
    except Exception as e:
        print(f"Error in evaluation: {str(e)}")
        return None

def switch_to_facet_account(page):
    """Switch to Facet account for commenting"""
    print("\nSwitching to Facet account...")
    
    try:
        # Click the account switcher button
        print("Looking for account switcher...")
        time.sleep(5)
        # while input("Type 'y' when ready to click account switcher: ").lower() != 'y':
        #     print("Please type 'y' when ready...")
            
        page.click('button[aria-label="Open menu for switching identity when interacting with this post"]')
        print("✓ Clicked account switcher")
        
        # Wait for modal to appear
        print("Waiting for account selection modal...")
        time.sleep(2)
        # while input("Type 'y' when account selection modal is visible: ").lower() != 'y':
        #     print("Please type 'y' when ready...")
        
        # Select Facet account - try multiple methods
        print("Selecting Facet account...")
        time.sleep(2)
        try:
            # First try clicking the entire row
            page.click('div.cursor-pointer:has-text("Facet")')
        except Exception:
            try:
                # Try clicking just the radio button
                page.click('input#select-runfacet')
            except Exception:
                try:
                    # Try clicking the label
                    page.click('label[for="select-runfacet"]')
                except Exception:
                    # Try evaluating JavaScript to select the radio
                    page.evaluate('''() => {
                        const radio = document.querySelector('input#select-runfacet');
                        if (radio) {
                            radio.checked = true;
                            radio.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }''')
        
        print("✓ Selected Facet account")
        
        # Wait a moment for the selection to register
        page.wait_for_timeout(1000)
        
        # Click Save button - try multiple selectors
        print("Looking for Save button...")
        save_selectors = [
            'button[aria-label="Save selection"]',
            'button:has-text("Save")',
            '.artdeco-modal__actionbar button.artdeco-button--primary'
        ]
        
        for selector in save_selectors:
            try:
                page.click(selector)
                print("✓ Clicked Save")
                break
            except Exception:
                continue
        
        # Wait for modal to close
        # while input("Type 'y' when account switch is complete: ").lower() != 'y':
        #     print("Please type 'y' when ready...")
            
        return True
        
    except Exception as e:
        print(f"✗ Error switching account: {str(e)}")
        return False

def main():
    debugging_port = get_chrome_debugging_port()
    if not debugging_port:
        return
    
    with sync_playwright() as p:
        try:
            # Connect to the existing Chrome instance
            browser = p.chromium.connect_over_cdp(f"http://localhost:{debugging_port}")
            print("✓ Connected to existing Chrome instance")
            
            # Get the first context (your main profile)
            context = browser.contexts[0]
            
            # Create a new page (tab) in the existing context
            page = context.new_page()
            page.set_viewport_size({"width": 1280, "height": 800})
            
            # Get all search queries and shuffle them
            queries = get_search_queries()
            random.shuffle(queries)  # Randomize query order
            print(f"\nLoaded and shuffled {len(queries)} search queries")
            
            # Process each query
            for query_index, query in enumerate(queries, 1):
                print(f"\n=== Processing Query {query_index}/{len(queries)} ===")
                print(f"Query: {query}")
                
                # Step 1: Search Google
                search_results = search_google_for_posts(page, query)
                if not search_results:
                    print("No results for this query, moving to next...")
                    continue
                
                # Step 2: Extract URLs
                urls = extract_linkedin_urls(search_results)
                if not urls:
                    print("No LinkedIn URLs found for this query, moving to next...")
                    continue
                
                # Process each URL from this query
                for url_index, url in enumerate(urls, 1):
                    print(f"\n--- Processing URL {url_index}/{len(urls)} ---")
                    print(f"URL: {url}")
                    
                    try:
                        # Step 3: Visit post
                        post_info = visit_linkedin_post(page, url)
                        if not post_info:
                            print("Couldn't process this post, moving to next...")
                            continue
                        
                        # Check if we've already commented
                        if check_if_already_commented(page):
                            print("Already commented on this post, moving to next...")
                            continue
                        
                        # Step 4: Prepare comment
                        comment = prepare_comment(post_info)
                        if not comment:
                            print("Couldn't generate comment, moving to next...")
                            continue
                        
                        # Get confirmation
                        should_post, final_comment = confirm_comment(post_info, comment)
                        if not should_post:
                            print("Skipping this post per user request...")
                            continue
                        
                        # Step 5: Post comment
                        success = post_comment(page, final_comment)
                        if success:
                            print("✓ Successfully commented on post!")
                        else:
                            print("✗ Failed to post comment")
                        
                    except Exception as e:
                        print(f"Error processing URL: {str(e)}")
                        continue
                    
           
                time.sleep(10)
                # Optional: Wait between queries
            
            print("\n=== Completed all queries ===")
            
        except Exception as e:
            print(f"Fatal error: {str(e)}")
        finally:
            if 'page' in locals():
                page.close()  # Only close our tab
            if 'browser' in locals():
                browser.disconnect()  # Just disconnect, don't close Chrome

if __name__ == "__main__":
    main() 