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

def has_existing_kwrds_comment(submission):
    submission.comments.replace_more(limit=None)  # Load all comments
    for comment in submission.comments.list():
        if "kwrds.ai" in comment.body.lower():
            print(f"Found existing kwrds.ai comment: {comment.body}")
            return True
    return False

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

def comment_on_post_by_id(reddit, post_id, comment_text):
    try:
        submission = reddit.submission(id=post_id)
        
        # Check relevance first
        if not is_post_relevant(submission):
            print("Skipping: Post not relevant to our topics")
            return False
        
        # Check for existing kwrds.ai comments
        if has_existing_kwrds_comment(submission):
            print("Skipping: Post already has a kwrds.ai comment")
            return False
        
        # If post is relevant and has no existing comment, post new comment
        submission.reply(comment_text)
        print(f"Successfully commented on post: {submission.title}")
        return True
        
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
        # Original queries
        'site:reddit.com "people also ask tool"',
        'site:reddit.com "people also ask"',
        'site:reddit.com "keyword research tool"',
        'site:reddit.com "keyword research"',
        'site:reddit.com "SERP analysis"',
        'site:reddit.com "SERP analysis tool"',
        'site:reddit.com "keyword tool"',
        'site:reddit.com "SEO tool"',
        'site:reddit.com "content research"',
        'site:reddit.com "search intent"',
        
        # New queries based on keyword data
        'site:reddit.com "people also ask tools"',
        'site:reddit.com "kwrds"',
        'site:reddit.com "people also ask keyword research tool"',
        'site:reddit.com "keyword volume checker"',
        'site:reddit.com "people also asked tool"',
        'site:reddit.com "search volume api"',
        'site:reddit.com "keyword tool ai"',
        'site:reddit.com "kwrds-ai"',
        'site:reddit.com "keyword volume"',
        'site:reddit.com "search volume tool"',
        
        # AI-focused queries
        'site:reddit.com "keyword research ai"',
        'site:reddit.com "ai seo tool"',
        'site:reddit.com "ai keyword tool"',
        'site:reddit.com "ai content tool"',
        
        # Additional variations
        'site:reddit.com "keyword research tools"',
        'site:reddit.com "keyword volume research"',
        'site:reddit.com "people also search for"',
        'site:reddit.com "keyword difficulty checker"',
        'site:reddit.com "search volume checker"',
        'site:reddit.com "keyword research platform"',
        'site:reddit.com "keyword suggestions"',
        'site:reddit.com "keyword ideas"'
    ]

def process_serp_results(reddit, comment_variations):
    """Process each SERP result immediately after finding it"""
    queries = get_search_queries()
    successful_comments = 0
    total_posts_found = 0
    processed_urls = set()  # Keep track of URLs we've already processed
    
    for query in queries:
        encoded_query = requests.utils.quote(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&tbs=qdr:d"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            print(f"\nSearching for: {query}")
            print(f"Google URL: {search_url}")
            response = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Process each result immediately
            for result in soup.find_all('a'):
                href = result.get('href', '')
                if 'reddit.com/r/' in href and '/comments/' in href:
                    clean_url = href.split('/url?q=')[1].split('&')[0] if '/url?q=' in href else href
                    
                    # Skip if we've already processed this URL
                    if clean_url in processed_urls:
                        print(f"Skipping already processed URL: {clean_url}")
                        continue
                    
                    processed_urls.add(clean_url)
                    total_posts_found += 1
                    
                    # Process the post immediately
                    post_id = extract_post_id_from_url(clean_url)
                    if post_id:
                        print(f"\nProcessing post: {clean_url}")
                        comment_text = random.choice(comment_variations)
                        if comment_on_post_by_id(reddit, post_id, comment_text):
                            successful_comments += 1
                            # Add delay between comments
                            time.sleep(15)  # 15 second delay between comments
            
            # Add delay between SERP queries
            print(f"Waiting before next search query...")
            time.sleep(30)  # 30 second delay between searches
            
        except Exception as e:
            print(f"Error processing query '{query}': {str(e)}")
            time.sleep(60)  # Longer delay if there's an error
            continue
    
    print(f"\nFinished processing all queries")
    print(f"Total posts found: {total_posts_found}")
    print(f"Successfully commented on {successful_comments} posts")

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
    
    # Process SERP results once
    try:
        print("\nStarting SERP processing...")
        process_serp_results(reddit, comment_variations)
        print("\nFinished all queries. Program complete.")
        
    except Exception as e:
        print(f"Error in main process: {str(e)}")


# TODO: https://www.google.com/search?q=site:reddit.com+%22keyword+research+tool%22&tbs=qdr:d
"this grabs query by day etc. Need to make this a cron job spammer every day"
"need to create multiple reddit accounts and rotate them to not be banned."