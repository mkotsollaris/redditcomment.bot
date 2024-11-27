import praw
import os
import pickle
from prawcore.exceptions import OAuthException
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import random

# File to store the refresh token
REFRESH_TOKEN_FILE = "refresh_token.pkl"

# Add at the top of the file with other globals
COMMENTED_POSTS = set()  # Track all posts we've commented on

def save_refresh_token(refresh_token):
    with open(REFRESH_TOKEN_FILE, 'wb') as f:
        pickle.dump(refresh_token, f)
        print("Token saved successfully!")

def load_refresh_token():
    try:
        with open(REFRESH_TOKEN_FILE, 'rb') as f:
            token = pickle.load(f)
            print("Found existing refresh token!")
            return token
    except FileNotFoundError:
        print("No existing refresh token found, need to authenticate")
        return None
    except Exception as e:
        print(f"Error loading token: {str(e)}")
        return None

def create_reddit_instance(refresh_token=None):
    reddit = praw.Reddit(
        client_id="CS_u0YgjKHTa6N52czUNVg",
        client_secret="38wzh_VnRWC2gM6eOlbcpJKTkbqURQ",
        user_agent="commentdemo/1.0 (by /u/Nicolas_JVM)",
        redirect_uri="https://www.google.com",
        refresh_token=refresh_token
    )
    return reddit

def authenticate():
    # Try to load existing refresh token
    print("Checking for existing refresh token...")
    refresh_token = load_refresh_token()
    if refresh_token:
        try:
            print("Attempting to use existing token...")
            reddit = create_reddit_instance(refresh_token)
            username = reddit.user.me().name
            print(f"Successfully authenticated as {username}!")
            return reddit
        except Exception as e:
            print(f"Saved token invalid or expired: {str(e)}")
            if os.path.exists(REFRESH_TOKEN_FILE):
                os.remove(REFRESH_TOKEN_FILE)
                print("Removed invalid token file")
    
    # If no token or token expired, do fresh authentication
    reddit = create_reddit_instance()
    scopes = ["submit", "read", "identity"]
    state = "random_string"
    auth_url = reddit.auth.url(scopes, state, "permanent")
    
    print("\nPlease follow these steps:")
    print("1. Visit this URL in your browser:")
    print(auth_url)
    print("\n2. Allow the app access to your Reddit account")
    print("3. You'll be redirected to Google. The URL will look like:")
    print("   https://www.google.com/?state=random_string&code=YOUR_CODE")
    print("4. Copy the ENTIRE URL you were redirected to")
    full_url = input("\nEnter the complete redirect URL: ")
    
    try:
        # Extract code from full URL
        if 'code=' in full_url:
            code = full_url.split('code=')[1].split('&')[0].split('#')[0]
            print(f"Extracted code: {code}")
        else:
            code = full_url  # In case user just pasted the code
        
        # Exchange the code for an access token
        refresh_token = reddit.auth.authorize(code)
        # Create a new instance with the refresh token
        reddit = create_reddit_instance(refresh_token)
        # Save the refresh token for future use
        save_refresh_token(refresh_token)
        print(f"Authentication successful as {reddit.user.me().name}!")
        return reddit
    except Exception as e:
        print(f"Authentication failed: {str(e)}")
        print("Please try again with a fresh authorization URL")
        raise

def has_existing_comment(submission, reddit):
    """Check if we've already commented on this submission"""
    try:
        submission.comments.replace_more(limit=0)
        my_username = reddit.user.me().name
        
        for comment in submission.comments.list():
            if comment.author and comment.author.name == my_username:
                print(f"Found existing comment by {my_username}")
                return True
        return False
        
    except Exception as e:
        print(f"Error checking existing comments: {str(e)}")
        return True  # Safer to return True on error

def is_post_relevant(submission):
    """Check if the post is relevant to our topics"""
    # Keywords that indicate relevance
    relevant_keywords = [
        'seo', 'keyword', 'serp', 'search engine', 'google',
        'content research', 'keyword research', 'people also ask',
        'search intent', 'search volume', 'ranking', 'traffic',
        'backlink', 'digital marketing', 'content strategy',
        'blog', 'content marketing', 'website traffic'
    ]
    
    # Keywords that indicate irrelevance
    irrelevant_keywords = [
        'nsfw', 'gaming', 'game', 'porn', 'dating',
        'relationship', 'personal', 'medical', 'health',
        'crypto', 'stock', 'trading', 'investment'
    ]
    
    # Get post content
    title = submission.title.lower()
    selftext = submission.selftext.lower()
    subreddit = submission.subreddit.display_name.lower()
    
    # Check subreddit first
    relevant_subreddits = {'seo', 'bigseo', 'marketing', 'digitalmarketing', 
                          'contentmarketing', 'blogging', 'entrepreneur', 
                          'smallbusiness', 'startups', 'webmarketing'}
    
    if subreddit in relevant_subreddits:
        return True
    
    # Check for irrelevant keywords first
    for keyword in irrelevant_keywords:
        if keyword in title or keyword in selftext:
            print(f"Post contains irrelevant keyword: {keyword}")
            return False
    
    # Check for relevant keywords
    relevant_count = 0
    for keyword in relevant_keywords:
        if keyword in title:
            relevant_count += 2  # Title matches are more important
        if keyword in selftext:
            relevant_count += 1
    
    # Require at least 2 relevance points
    is_relevant = relevant_count >= 2
    if not is_relevant:
        print(f"Post not relevant enough (score: {relevant_count})")
    else:
        print(f"Post is relevant (score: {relevant_count})")
    
    return is_relevant

def confirm_comment(subreddit, title, comment_text, post_url=None):
    """Ask for confirmation before posting a comment, with option to regenerate"""
    while True:
        print("\n=== Comment Confirmation ===")
        print(f"Subreddit: r/{subreddit}")
        print(f"Post: {title}")
        if post_url:
            print(f"URL: https://reddit.com{post_url}")
        print(f"Comment: {comment_text}")
        print("\nPress 'y' to confirm, 'r' to regenerate, any other key to skip: ")
        
        confirmation = input().lower()
        if confirmation == 'y':
            return True, comment_text
        elif confirmation == 'r':
            print("Regenerating comment...")
            return False, "regenerate"
        else:
            return False, None

def validate_comment_has_link(comment):
    """Check if comment has proper markdown link to kwrds.ai"""
    return '](https://www.kwrds.ai)' in comment

def clean_comment_text(comment):
    """Clean the comment text by removing explanatory notes and meta-commentary"""
    # Split on common separators that might indicate explanatory text
    separators = [
        "\nThis response",
        "\nNote:",
        "\nExplanation:",
        "\nReasoning:",
        "This comment",
        "This response",
        "Here's a possible comment:",
        "Here's a comment:",
        "Possible response:",
        "I would say:",
        "I would comment:",
        "Here's what I'd say:",
        "Generated comment:"
    ]
    
    for separator in separators:
        if separator.lower() in comment.lower():
            comment = comment.split(separator)[1] if separator in comment else comment.split(separator.lower())[1]
    
    # Remove any trailing whitespace and leading newlines
    comment = comment.strip()
    while comment.startswith('\n'):
        comment = comment[1:]
    
    return comment.strip()

def comment_on_post_by_id(reddit, post_id, comment_text):
    try:
        submission = reddit.submission(id=post_id)
        
        if has_existing_comment(submission, reddit):
            print("Skipping: Already commented on this post")
            return False
        
        if not is_post_relevant(submission):
            print("Skipping: Post not relevant to our topics")
            return False
        
        while True:  # Loop for regenerating comments
            max_attempts = 3
            for attempt in range(max_attempts):
                comment_text = generate_engaging_comment(prompt)
                if comment_text:
                    comment_text = clean_comment_text(comment_text)
                    if validate_comment_has_link(comment_text):
                        break
                print(f"Generated comment missing proper link format, attempt {attempt + 1}/{max_attempts}")
            
            if not comment_text or not validate_comment_has_link(comment_text):
                print("Failed to generate comment with proper link format")
                return False
                
            # Ask for confirmation with regeneration option
            confirmed, result = confirm_comment(submission.subreddit.display_name, 
                                             submission.title, 
                                             comment_text, 
                                             submission.permalink)
            
            if confirmed:
                submission.reply(comment_text)
                print(f"Successfully commented on post: {submission.title}")
                return True
            elif result == "regenerate":
                print("Regenerating comment...")
                continue
            else:
                print("Comment skipped by user")
                return False
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def extract_post_id_from_url(url):
    try:
        # Reddit URLs usually have /comments/POST_ID/
        if '/comments/' in url:
            return url.split('/comments/')[1].split('/')[0]
        return None
    except:
        return None

def get_search_queries():
    """Return a list of search queries to target different keywords"""
    return [
        # Core kwrds.ai features
        'site:reddit.com "people also ask tool"',
        'site:reddit.com "people also ask data"',
        'site:reddit.com "people also search for"',
        'site:reddit.com "search intent tool"',
        'site:reddit.com "SERP analysis tool"',
        
        # Keyword Research
        'site:reddit.com "keyword research tool"',
        'site:reddit.com "AI keyword research"',
        'site:reddit.com "keyword research automation"',
        'site:reddit.com "best keyword research tool"',
        'site:reddit.com "keyword difficulty checker"',
        'site:reddit.com "keyword clustering tool"',
        'site:reddit.com "long tail keywords tool"',
        
        # SEO Tools
        'site:reddit.com "SEO tool recommendation"',
        'site:reddit.com "AI SEO tool"',
        'site:reddit.com "SERP features tool"',
        'site:reddit.com "search volume tool"',
        'site:reddit.com "keyword tracking tool"',
        
        # Content Strategy
        'site:reddit.com "content gap analysis"',
        'site:reddit.com "content research tool"',
        'site:reddit.com "topic research tool"',
        'site:reddit.com "content optimization tool"',
        'site:reddit.com "content strategy tool"',
        
        # Search Intent
        'site:reddit.com "search intent analysis"',
        'site:reddit.com "user intent tool"',
        'site:reddit.com "keyword intent"',
        'site:reddit.com "search intent optimization"',
        
        # Questions and PAA
        'site:reddit.com "find question keywords"',
        'site:reddit.com "question keyword tool"',
        'site:reddit.com "find what people ask"',
        'site:reddit.com "question research tool"',
        
        # Specific Subreddits
        'site:reddit.com/r/SEO "keyword tool"',
        'site:reddit.com/r/bigseo "keyword research"',
        'site:reddit.com/r/contentmarketing "keyword research"',
        'site:reddit.com/r/juststart "keyword research tool"',
        'site:reddit.com/r/blogging "keyword research"'
    ]

def get_random_proxy():
    """Get a random proxy from the list and format it properly"""
    prox_list = [
        'geo.iproyal.com:12321:raVWrZ8duQaStI6t:r79i2q51TaQHYmy1_country-us',
        'us.smartproxy.com:10000:sprkucstlr:gd3patxyW6Dln73YpG',
        'pr.oxylabs.io:7777:kwrds_ai_mk:fLeYms_pd_d6PA2',
        'brd.superproxy.io:22225:brd-customer-hl_5a8e7459-zone-kwrz_residential_rotating:d48umurinii2'
    ]
    
    proxy = random.choice(prox_list)
    host, port, user, password = proxy.split(':')
    
    return {
        'http': f'http://{user}:{password}@{host}:{port}',
        'https': f'http://{user}:{password}@{host}:{port}'
    }

def get_hobby_subreddits():
    """Return a list of hobby/casual subreddits to post in, with extra weight for cat subs"""
    return [
        # Cat subreddits (repeated to increase probability)
        'cats', 'cats', 'cats',  # Triple weight for r/cats
        'CatPics', 'CatPics',
        'catpictures',
        'CatsStandingUp',
        'CatsWithJobs',
        'IllegallySmolCats',
        # Other pets
        'dogs', 'Pets', 'aww',
        # Other hobbies
        'gardening', 'houseplants',
        'cooking', 'food',
        'photography', 'itookapicture',
        'DIY', 'crafts',
        'hiking', 'camping',
        'books', 'reading'
    ]

def get_casual_comments():
    """Return a list of casual comments with extra cat-focused ones"""
    return [
        # Cat-specific comments
        "What a beautiful kitty! How old is she/he?",
        "Those eyes are mesmerizing! What's your cat's name?",
        "Such a gorgeous cat! Is it a specific breed?",
        "Adorable! My cat does the exact same thing.",
        "That's one photogenic cat! Great shot.",
        # General comments
        "Beautiful photo! What camera did you use?",
        "This is amazing! How long did it take you?",
        "Love this! Do you have any tips for beginners?",
        "Wow, great work! Thanks for sharing.",
        "Really nice! What inspired you?",
        "Incredible work! Would love to learn more about your process.",
        "Beautiful! Where was this taken?",
        "Very impressive! How did you learn?"
    ]

def generate_engaging_comment(prompt):
    """Generate an engaging comment using Ollama's Llama3.2"""
    try:
        response = requests.post('http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2',
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'top_k': 50,
                    'top_p': 0.9,
                    'max_length': 100
                }
            }
        )
        if response.status_code == 200:
            # Clean up the response by removing unnecessary quotes
            comment = response.json()['response'].strip()
            comment = comment.strip('"')  # Remove surrounding quotes
            comment = comment.replace('\"', '')  # Remove any remaining quotes
            return comment
        return None
    except Exception as e:
        print(f"Error generating comment: {str(e)}")
        return None

def make_random_hobby_comment(reddit):
    """Make a random comment in a hobby subreddit without requiring confirmation"""
    try:
        subreddit_name = random.choice(get_hobby_subreddits())
        subreddit = reddit.subreddit(subreddit_name)
        
        hot_posts = list(subreddit.hot(limit=20))
        post = random.choice(hot_posts)
        
        if has_existing_comment(post, reddit):
            print(f"Already commented in this post in r/{subreddit_name}")
            return False
        
        # Updated prompt to be more casual and allow occasional emojis
        prompt = f"""Write a super casual, friendly Reddit comment (1-2 sentences) for this post. Sound like a real Redditor - be enthusiastic but natural.
        Sometimes (20% chance) include ONE simple emoji like ❤️ 🐱 🌿 📸 ✨

        Subreddit: {subreddit_name}
        Title: {post.title}
        Content: {post.selftext[:200] if post.selftext else '[image/link post]'}
        
        Examples:
        - "omg what a gorgeous kitty! what's their name? ❤️"
        - "this is amazing! would love to try this recipe"
        - "wow those colors are incredible ✨"
        - "your garden is goals! 🌿"
        """
        
        comment_text = generate_engaging_comment(prompt)
        if comment_text:
            # Clean the comment before posting
            comment_text = clean_comment_text(comment_text)
        else:
            comment_text = random.choice(get_casual_comments())
        
        print("\n=== Hobby Comment Info ===")
        print(f"Subreddit: r/{subreddit_name}")
        print(f"Post: {post.title}")
        print(f"URL: https://reddit.com{post.permalink}")
        print(f"Comment: {comment_text}")
            
        post.reply(comment_text)
        print(f"Made AI-generated hobby comment in r/{subreddit_name}")
        return True
        
    except Exception as e:
        print(f"Error making hobby comment: {str(e)}")
        return False

def should_make_hobby_comment():
    """Decide if we should make a hobby comment (increased to 70% chance)"""
    return random.random() < 0.7  # Increased from 0.5 to 0.7

def process_serp_results(reddit, comment_variations):
    """Process each SERP result immediately after finding it"""
    queries = get_search_queries()
    successful_comments = 0
    total_posts_found = 0
    processed_urls = set()
    seo_comments_since_hobby = 0  # Track SEO comments since last hobby comment
    
    # Start with just one hobby comment
    print("\nMaking initial hobby comment...")
    make_random_hobby_comment(reddit)
    time.sleep(30)
    
    for query in queries:
        # Force hobby comment if we've made 2-3 SEO comments without one
        if seo_comments_since_hobby >= random.randint(2, 3):
            print("\nMaking a hobby comment after several SEO comments...")
            make_random_hobby_comment(reddit)
            print("Waiting 30 seconds after hobby comment...")
            time.sleep(30)
            seo_comments_since_hobby = 0  # Reset counter
        
        encoded_query = requests.utils.quote(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&tbs=qdr:y"  # Yearly results
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Try up to 3 different proxies for each query
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"\nSearching for: {query}")
                print(f"Google URL: {search_url}")
                print(f"Attempt {attempt + 1} of {max_retries}")
                
                proxies = get_random_proxy()
                print(f"Using proxy: {proxies['http'].split('@')[1]}")
                
                response = requests.get(
                    search_url, 
                    headers=headers, 
                    proxies=proxies,
                    timeout=5
                )
                print(f"Response status code: {response.status_code}")
                
                if response.status_code != 200:
                    raise Exception(f"Bad status code: {response.status_code}")
                
                break
                
            except Exception as e:
                print(f"Proxy attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    print("All proxy attempts failed, skipping query")
                    continue
                time.sleep(5)
        else:
            continue
            
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            all_links = soup.find_all('a')
            reddit_links = [link for link in all_links if 'reddit.com/r/' in str(link.get('href', ''))]
            
            if len(reddit_links) == 0:
                print("No Reddit posts found for this query")
                print(f"Waiting before next search query...")
                time.sleep(10)
                continue
            
            print(f"Found {len(reddit_links)} Reddit links")
            
            # Process each result immediately
            reddit_posts_found = 0
            comments_this_query = 0
            for result in all_links:
                href = result.get('href', '')
                if 'reddit.com/r/' in href and '/comments/' in href:
                    reddit_posts_found += 1
                    clean_url = href.split('/url?q=')[1].split('&')[0] if '/url?q=' in href else href
                    
                    if clean_url in processed_urls:
                        print(f"Skipping already processed URL: {clean_url}")
                        continue
                    
                    processed_urls.add(clean_url)
                    total_posts_found += 1
                    print(f"Found Reddit post: {clean_url}")
                    
                    post_id = extract_post_id_from_url(clean_url)
                    if post_id:
                        print(f"\nProcessing post: {clean_url}")
                        comment_text = random.choice(comment_variations)
                        if comment_on_post_by_id(reddit, post_id, comment_text):
                            successful_comments += 1
                            comments_this_query += 1
                            seo_comments_since_hobby += 1  # Increment counter after successful comment
                            print(f"Successfully commented on post {post_id}")
                            time.sleep(10)
            
            if reddit_posts_found > 0:
                print(f"Query results: Found {reddit_posts_found} posts, successfully commented on {comments_this_query}")
                print(f"Running totals: Found {total_posts_found} posts, commented on {successful_comments}")
            
            print(f"Waiting before next search query...")
            time.sleep(10)
            
        except Exception as e:
            print(f"Error processing query '{query}': {str(e)}")
            print(f"Full error: {str(e.__class__.__name__)}: {str(e)}")
            time.sleep(60)
            continue
    
    print(f"\nFinished processing all queries")
    if total_posts_found > 0:
        print(f"Final results:")
        print(f"Total posts found: {total_posts_found}")
        print(f"Successfully commented on: {successful_comments}")
        print(f"Success rate: {(successful_comments/total_posts_found)*100:.1f}%")
    else:
        print("No posts were found during this run")

def get_comment_variations():
    """Return a list of natural-sounding comment variations with AI references"""
    return [
        "Found this [AI keyword research tool](https://www.kwrds.ai) pretty useful",
        "Been using this [AI-powered people also ask tool](https://www.kwrds.ai) lately",
        "Try this [AI SEO tool](https://www.kwrds.ai) for keyword research",
        "Here's a good [AI SERP keyword research tool](https://www.kwrds.ai) I found",
        "This [AI keyword research tool](https://www.kwrds.ai) helped me a lot",
        "Check out this [AI people also ask analyzer](https://www.kwrds.ai)",
        "Found a neat [AI keyword research](https://www.kwrds.ai) tool",
        "This [AI content research tool](https://www.kwrds.ai) is pretty good",
        "Helpful [AI SEO research tool](https://www.kwrds.ai) right here",
        "Try this [AI-driven keyword tool](https://www.kwrds.ai)",
        "Great [AI search intent tool](https://www.kwrds.ai) I discovered",
        "This [AI keyword analyzer](https://www.kwrds.ai) is pretty solid",
        "Found an [AI SEO keyword research assistant](https://www.kwrds.ai) that works well",
        "Nice [AI content optimization tool](https://www.kwrds.ai) here",
        "Check this [AI keyword intelligence tool](https://www.kwrds.ai)",
        "Using this [AI search analysis tool](https://www.kwrds.ai) lately",
        "Solid [AI keyword research platform](https://www.kwrds.ai)",
        "This [AI SEO research tool](https://www.kwrds.ai) is helpful",
        "Found a good [AI search insights tool](https://www.kwrds.ai)",
        "Try this [AI keyword discovery tool](https://www.kwrds.ai)"
    ]

# Update the main section
if __name__ == "__main__":
    print("Starting authentication process...")
    reddit = authenticate()
    
    # Get comment variations
    comment_variations = get_comment_variations()
    
    # Maybe start with a hobby comment
    if should_make_hobby_comment():
        print("\nStarting with a casual hobby comment...")
        make_random_hobby_comment(reddit)
        time.sleep(15)  # Wait 5-10 minutes
    
    # Process SERP results
    try:
        print("\nStarting SERP processing...")
        process_serp_results(reddit, comment_variations)
        
        # Maybe end with a hobby comment
        if should_make_hobby_comment():
            print("\nEnding with a casual hobby comment...")
            make_random_hobby_comment(reddit)
            
        print("\nFinished all queries. Program complete.")
        
    except Exception as e:
        print(f"Error in main process: {str(e)}")


# TODO: https://www.google.com/search?q=site:reddit.com+%22keyword+research+tool%22&tbs=qdr:d
"add multiple accounts and rotate"