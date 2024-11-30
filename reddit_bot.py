import praw  # Instead of asyncpraw
import os
import pickle
from prawcore.exceptions import OAuthException
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import random
import signal
from contextlib import contextmanager
import openai
from typing import Optional, Tuple, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# File to store the refresh token
REFRESH_TOKEN_FILE = "refresh_token.pkl"

# Add at the top of the file with other globals
COMMENTED_POSTS = set()  # Track all posts we've commented on

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")
openai.api_key = OPENAI_API_KEY
print(f"Using OpenAI API key: {OPENAI_API_KEY}")

@contextmanager
def timeout(seconds):
    def timeout_handler(signum, frame):
        raise TimeoutError("Input timed out")
    
    # Set the timeout handler
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Disable the alarm
        signal.alarm(0)

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
        print("\nPress 'y' to confirm, 'r' to regenerate, any other key to skip (70s timeout = confirm): ")
        
        try:
            with timeout(70):  # 70 second timeout
                confirmation = input().lower()
        except TimeoutError:
            print("\nInput timed out - automatically confirming comment")
            return True, comment_text
        
        if confirmation == 'y':
            return True, comment_text
        elif confirmation == 'r':
            print("Regenerating comment...")
            return True, "regenerate"
        else:
            return False, None

def validate_comment_has_link(comment):
    """Check if comment has proper markdown link to kwrds.ai"""
    return '](https://www.kwrds.ai)' in comment

def clean_comment_text(comment):
    """Clean and casualize the comment text"""
    # First do the existing cleaning
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
        "Generated comment:",
        "Here are a few options:",
        "Option 1:",
        "Option 2:",
        "Option 3:",
        "* ",  # Remove bullet points
        "- ",  # Remove dashes
        "\n\n"  # Remove double newlines
    ]
    
    # First split by any separator
    for separator in separators:
        if separator.lower() in comment.lower():
            parts = comment.split(separator, 1)
            comment = parts[-1]  # Take the last part after the separator
    
    # Clean up the text
    comment = comment.strip()
    
    # Remove any remaining bullet points or numbered lists
    lines = comment.split('\n')
    cleaned_lines = [line.strip() for line in lines if not line.strip().startswith(('*', '-', '1.', '2.', '3.'))]
    
    # Take only the first non-empty line
    for line in lines:
        if line:
            comment = line
            break
    
    # Make the comment more casual:
    
    # 1. Randomly remove some commas (70% chance to remove each comma)
    words = comment.split()
    casual = ""
    for i, word in enumerate(words):
        if word.endswith(',') and random.random() < 0.7:
            casual += word[:-1] + ' '
        else:
            casual += word + ' '
    
    # 2. Sometimes use lowercase at start (30% chance)
    if random.random() < 0.3:
        casual = casual[0].lower() + casual[1:]
    
    # 3. Sometimes skip periods at end (40% chance)
    if casual.endswith('.') and random.random() < 0.4:
        casual = casual[:-1]
    
    # 4. Sometimes add multiple exclamation points (20% chance)
    if casual.endswith('!') and random.random() < 0.2:
        casual += '!'
    
    # 5. Sometimes add ... (15% chance)
    if random.random() < 0.15:
        casual += '...'
    
    # 6. Sometimes use lowercase i instead of I (50% chance for each)
    casual = ' '.join(word if word != 'I' or random.random() > 0.5 else 'i' 
                     for word in casual.split())
    
    return casual.strip()

def generate_comment(submission, max_attempts=5) -> Optional[str]:
    """Generate a contextual comment using ChatGPT with multiple attempts"""
    best_comment = None
    best_score = 0
    
    for attempt in range(max_attempts):
        try:
            print(f"\nAttempt {attempt + 1} to generate comment...")
            
            # Safely get post details
            post_content = getattr(submission, 'selftext', '')
            post_url = getattr(submission, 'url', '')
            author_name = submission.author.name if getattr(submission, 'author', None) else '[deleted]'
            score = getattr(submission, 'score', 0)
            created = getattr(submission, 'created_utc', 'unknown')
            is_self = getattr(submission, 'is_self', True)
            
            prompt = f"""You are a chill SEO dude on Reddit who talks casually using modern internet slang. Keep responses short and to the point.

Context:
Subreddit: r/{submission.subreddit.display_name}
Post Title: {submission.title}
Post Content: {post_content}
Post URL: {post_url}
Post Author: u/{author_name}
Post Score: {score}
Post Age: {created}
Is Text Post: {is_self}

{f"Link Content: {post_url}" if not is_self else ""}

Writing style:
- Super casual, like talking to friends
- Keep responses SHORT (1-2 short paragraphs max)
- One main point per response
- Get to the point quickly
- Mix up your conversation starters
- For SEO/keyword related posts: Always include a tool mention
- For non-SEO posts: Casually mention tools ~50% of the time if relevant
- When mentioning tools:
  * SEO posts: Use hyperlink [kwrds.ai](https://www.kwrds.ai)
  * Non-SEO posts: Just mention kwrds.ai naturally without link

Natural tool mention examples for SEO posts:
- "found [this tool](https://www.kwrds.ai) super helpful for that"
- "[kwrds.ai](https://www.kwrds.ai) helped me figure this out"
- "try [this seo tool](https://www.kwrds.ai) - made it easier for me"

Casual mentions for non-SEO posts (no links):
- "reminds me of what i saw on kwrds.ai the other day"
- "kwrds.ai shows similar patterns"
- "saw something like this on kwrds.ai recently"

Remember: Quick, helpful responses that get straight to the point.

Write a short, casual response:"""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a casual Redditor quickly typing out comments. You occasionally mention tools that might help, but you're mainly just chatting with other SEOs."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,
                max_tokens=500
            )
            
            comment = response.choices[0].message.content.strip()
            
            # Adjust scoring to favor shorter comments
            score = 0
            
            # Basic validations that must pass
            if len(comment) > 800:  # Reduced from 1500
                print("Comment too long, trying again...")
                continue
            
            if len(comment) < 50:
                print("Comment too short, trying again...")
                continue

            # Bonus points for concise comments
            if len(comment) < 400:
                score += 10  # Bonus for very concise comments
            elif len(comment) < 600:
                score += 5   # Small bonus for moderately sized comments
            
            # Score different aspects
            score += 10 if not any(x in comment.lower() for x in ['hey u/', 'hi u/', 'hello u/', ' u/']) else 0
            score += 10 if not comment.lower().startswith(('thanks', 'great post', 'nice post', 'hey there')) else 0
            
            # Check links and tool mentions
            raw_mentions = comment.lower().count('kwrds.ai')
            linked_mentions = sum([
                comment.lower().count('](https://www.kwrds.ai)'),
                comment.lower().count('](http://www.kwrds.ai)'),
                comment.lower().count('](kwrds.ai)'),
                len([m for m in comment.lower().split('[') 
                    if ']' in m and 'kwrds.ai' in m and '](http' in m.lower()])
            ])
            
            # Tool mention scoring (max 30 points)
            is_seo_related = any(x in submission.title.lower() or x in submission.selftext.lower() 
                                for x in ['seo', 'keyword', 'search', 'content', 'ranking'])
            
            if raw_mentions == 0:
                if is_seo_related:
                    score += 0  # No tool mention in SEO post = no points
                else:
                    score += 15  # No tool mention in non-SEO post = partial points
            elif raw_mentions == linked_mentions and raw_mentions == 1:
                if is_seo_related:
                    score += 30  # Perfect - one properly linked mention in SEO post
                else:
                    score += 20  # Linked mention in non-SEO post
            elif raw_mentions == 1:  # Unlinked mention
                if is_seo_related:
                    score += 10  # Unlinked mention in SEO post
                else:
                    score += 25  # Unlinked mention in non-SEO post (preferred)
            
            # Check promotional language
            promo_phrases = [
                'amazing tool', 'best tool', 'must-try',
                'game changer', 'incredible tool', 'revolutionary'
            ]
            score += 10 if not any(phrase in comment.lower() for phrase in promo_phrases) else 0
            
            # Check formal language
            formal_phrases = [
                'please find', 'i am pleased to',
                'we offer', 'our solution'
            ]
            score += 10 if not any(phrase in comment.lower() for phrase in formal_phrases) else 0
            
            print(f"Comment score: {score}/70")
            print(f"Tool mentions: {raw_mentions} (linked: {linked_mentions})")
            
            # Keep track of best comment
            if score > best_score:
                best_score = score
                best_comment = comment
                print("New best comment found!")
            
            # Perfect score requires tool mention
            if score == 70 and linked_mentions == 1:
                return comment
            
            # If this isn't the last attempt, continue trying for a better comment
            if attempt < max_attempts - 1 and score < 50:
                continue
                
        except Exception as e:
            print(f"Error in generation attempt {attempt + 1}: {str(e)}")
            if attempt == max_attempts - 1 and best_comment is None:
                return None
            time.sleep(1)
    
    # Return best comment if it meets minimum threshold
    if best_comment and best_score >= 40:  # Adjust threshold as needed
        print(f"Using best comment (score: {best_score}/70)")
        return best_comment
    
    return None

def evaluate_comment(comment: str, post_context: str, max_attempts=3) -> Optional[Dict[str, Any]]:
    """Evaluate comment quality with multiple attempts"""
    for attempt in range(max_attempts):
        try:
            evaluation_prompt = f"""Evaluate this Reddit comment and decide if the kwrds.ai tool mention should stay or be removed.

Post Context:
{post_context}

Comment to evaluate:
{comment}

Evaluation criteria:
1. Is the post about SEO/keywords/content strategy? (More likely to keep tool mention)
2. Is the author asking for tool recommendations? (More likely to keep)
3. Does the tool mention feel natural in context? (Required to keep)
4. Would removing the tool mention make the comment better? (If yes, remove)

Score each aspect (1-10) and decide if the tool mention should stay.
If removing, provide the exact comment text minus the tool mention.

Return in Python dictionary format:
{{
    "scores": {{
        "naturalness": X,
        "relevance": X,
        "tool_mention": X,
        "engagement": X
    }},
    "should_regenerate": False,
    "keep_tool_mention": True/False,  # New field
    "clean_comment": "comment text with tool mention removed if needed",
    "reason": "explanation for decision",
    "improvement_suggestions": "suggestions if needed"
}}"""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at evaluating Reddit comment quality and authenticity."},
                    {"role": "user", "content": evaluation_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            evaluation_str = response.choices[0].message.content.strip()
            
            # Clean up the response to ensure Python compatibility
            evaluation_str = evaluation_str.replace('true', 'True').replace('false', 'False')
            
            try:
                # Safely evaluate the string as Python code
                evaluation = eval(evaluation_str)
                
                # Validate the required keys exist
                required_keys = ['scores', 'should_regenerate', 'reason']
                if not all(key in evaluation for key in required_keys):
                    print("Missing required keys in evaluation")
                    return None
                    
                # Validate scores exist and are numbers
                required_scores = ['naturalness', 'relevance', 'tool_mention', 'engagement']
                if not all(key in evaluation['scores'] for key in required_scores):
                    print("Missing required scores in evaluation")
                    return None
                    
                return evaluation

            except (SyntaxError, NameError) as e:
                print(f"Error parsing evaluation response: {str(e)}")
                print(f"Raw response: {evaluation_str}")
                return None

        except Exception as e:
            print(f"Error in evaluation attempt {attempt + 1}: {str(e)}")
            if attempt == max_attempts - 1:
                return None
            time.sleep(1)
    
    return None

def should_regenerate_comment(evaluation: Dict[str, Any]) -> Tuple[bool, str]:
    """Determine if comment should be regenerated based on evaluation scores"""
    if not evaluation:
        return True, "Evaluation failed"
        
    scores = evaluation['scores']
    
    # Calculate weighted average score
    weights = {
        'naturalness': 0.35,
        'relevance': 0.30,
        'tool_mention': 0.25,  # Increased weight for tool mentions
        'engagement': 0.10
    }
    
    weighted_score = sum(scores[k] * weights[k] for k in weights)
    
    # Stricter regeneration triggers
    if (scores['naturalness'] < 7.5 or  # Increased threshold
        scores['relevance'] < 7.0 or    # Increased threshold
        scores['tool_mention'] < 7.0 or  # Added tool mention threshold
        weighted_score < 7.5):          # Increased threshold
        return True, evaluation.get('reason', 'Scores below threshold')
        
    return False, ''

def comment_on_post_by_id(reddit, post_id, comment_text=None):
    try:
        submission = reddit.submission(id=post_id)
        
        # Check if post is archived
        if submission.archived:
            print("Skipping: Post is archived")
            return False
        
        if has_existing_comment(submission, reddit):
            print("Skipping: Already commented on this post")
            return False
        
        if not is_post_relevant(submission):
            print("Skipping: Post not relevant to our topics")
            return False
            
        for attempt in range(5):  # Maximum 5 attempts per post
            print(f"\nGeneration attempt {attempt + 1}")
            
            comment_text = generate_comment(submission)
            if not comment_text:
                print("Failed to generate appropriate comment")
                return False
            
            post_context = f"""
            Subreddit: r/{submission.subreddit.display_name}
            Title: {submission.title}
            Content: {submission.selftext[:300] if submission.selftext else '[No text content]'}
            """
            evaluation = evaluate_comment(comment_text, post_context)
            if not evaluation:
                print("Failed to evaluate comment")
                continue
            
            if evaluation:
                print("\nEvaluation scores:")
                for key, score in evaluation['scores'].items():
                    print(f"- {key.title()}: {score}/10")
                
                if not evaluation.get('keep_tool_mention', True):
                    print("\nRemoving tool mention as per evaluation")
                    comment_text = evaluation['clean_comment']
            
            should_regen, reason = should_regenerate_comment(evaluation)
            
            if should_regen:
                print(f"\nRetrying: {reason}")
                continue
            
            print("\nComment passed quality checks!")
            
            # Human confirmation
            confirmed, final_comment = confirm_comment(
                submission.subreddit.display_name, 
                submission.title, 
                comment_text, 
                submission.permalink
            )
            
            if not confirmed:
                return False
                
            if final_comment == "regenerate":
                continue
                
            submission.reply(final_comment)
            print(f"Successfully commented on post: {submission.title}")
            return True
            
        print("Maximum attempts reached without success")
        return False
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def extract_post_id_from_url(url):
    try:
        # Reddit URLs usually have /comments/POST_ID/
        if '/comments/' in url:
            return url.split('/comments/')[1].split('/')[0]
        return None
    except:
        return None

"TODO use LSI and keyword research from internal endpoint"
def get_search_queries():
    """Return a list of search queries to target different keywords"""
    
    # Add new keyword research variations
    keyword_research_queries = [
        'site:reddit.com "keyword research"',
        'site:reddit.com "keyword analysis tools free"',
        'site:reddit.com "keyword research tools free"',
        'site:reddit.com "tools for keyword research"',
        'site:reddit.com "keyword research in seo"',
        'site:reddit.com "keyword research for youtube"',
        'site:reddit.com "keyword research and seo"',
        'site:reddit.com "keyword research google tool"',
        'site:reddit.com "how do i do keyword research"',
        'site:reddit.com "how to keyword research"',
        'site:reddit.com "how to conduct keyword research"',
        'site:reddit.com "how do keyword research"',
        'site:reddit.com "how to do keyword research"',
        'site:reddit.com "how to do keyword analysis"',
        'site:reddit.com "best tools for keyword research"',
        'site:reddit.com "semrush keyword research"',
        'site:reddit.com "keyword research tools seo"',
        'site:reddit.com "keywords for pinterest"',
        'site:reddit.com "ahrefs keyword research"'
    ]
    
    # Combine with existing queries
    return [
        # New keyword research queries
        *keyword_research_queries,
        
        # Core kwrds.ai features
        'site:reddit.com "people also ask tool"',
        'site:reddit.com "people also ask data"',
        'site:reddit.com "people also search for"',
        'site:reddit.com "search intent tool"',
        'site:reddit.com "SERP analysis tool"',
        
        # New PAA-specific queries
        'site:reddit.com "how to find question keywords"',
        'site:reddit.com "question keyword research"',
        'site:reddit.com "find user questions"',
        'site:reddit.com "question based content"',
        'site:reddit.com "question keyword tool"',
        
        # Search Intent focused
        'site:reddit.com "understand search intent"',
        'site:reddit.com "search intent analysis"',
        'site:reddit.com "user intent research"',
        'site:reddit.com "keyword intent tool"',
        'site:reddit.com "content intent"',
        
        # SERP Features
        'site:reddit.com "SERP feature analysis"',
        'site:reddit.com "SERP position tracking"',
        'site:reddit.com "SERP competition analysis"',
        'site:reddit.com "featured snippet optimization"',
        'site:reddit.com "rich results seo"',
        
        # Existing Keyword Research
        'site:reddit.com "keyword research tool"',
        'site:reddit.com "AI keyword research"',
        'site:reddit.com "keyword research automation"',
        'site:reddit.com "best keyword research tool"',
        'site:reddit.com "keyword difficulty checker"',
        
        # Content Strategy
        'site:reddit.com "content gap analysis"',
        'site:reddit.com "content research tool"',
        'site:reddit.com "content optimization tool"',
        'site:reddit.com "content strategy tool"',
        'site:reddit.com "content planning tool"',
        
        # Specific Subreddits with topic focus
        'site:reddit.com/r/SEO "question research"',
        'site:reddit.com/r/bigseo "search intent"',
        'site:reddit.com/r/contentmarketing "people also ask"',
        'site:reddit.com/r/juststart "keyword research"',
        'site:reddit.com/r/blogging "content research"',
        'site:reddit.com/r/marketing "SEO tools"',
        
        # AI SEO specific
        'site:reddit.com "AI content optimization"',
        'site:reddit.com "AI SEO tool"',
        'site:reddit.com "AI keyword analysis"',
        'site:reddit.com "machine learning SEO"',
        'site:reddit.com "AI content research"',
        
        # High-volume SEO queries
        'site:reddit.com "keyword research"',
        'site:reddit.com "SEO tools"',
        'site:reddit.com "SEO software"',
        'site:reddit.com "rank tracking"',
        'site:reddit.com "keyword tracking"',
        'site:reddit.com "SEO recommendations"',
        
        # Question/Content Research
        'site:reddit.com "how to research keywords"',
        'site:reddit.com "find content ideas"',
        'site:reddit.com "content research"',
        'site:reddit.com "blog topic ideas"',
        'site:reddit.com "content planning"',
        
        # Popular Subreddit Queries
        'site:reddit.com/r/SEO "tool recommendation"',
        'site:reddit.com/r/bigseo "tools"',
        'site:reddit.com/r/Blogging "SEO help"',
        'site:reddit.com/r/juststart "keyword tools"',
        'site:reddit.com/r/marketing "SEO software"',
        
        # General SEO Help
        'site:reddit.com "need SEO help"',
        'site:reddit.com "SEO beginner"',
        'site:reddit.com "SEO advice"',
        'site:reddit.com "keyword help"',
        'site:reddit.com "content strategy help"'
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
        
        # Updated prompt to be explicit about single response while keeping examples
        prompt = f"""Write ONE single casual Reddit comment (1-2 sentences) for this post. Do not provide multiple options or explanations.

        Subreddit: {subreddit_name}
        Title: {post.title}
        Content: {post.selftext[:200] if post.selftext else '[image/link post]'}
        
        Rules:
        - Write exactly ONE comment
        - No bullet points or lists
        - No explanations or notes
        - Be casual and natural
        - Sometimes (20% chance) include ONE emoji like ❤️ 🐱 🌿 📸 ✨

        Example style (don't copy, just follow the tone):
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
    return random.random() < 0.85  # Increased from 0.5 to 0.7

def process_serp_results(reddit):
    """Process each SERP result immediately after finding it"""
    queries = get_search_queries()
    # Shuffle the queries randomly
    random.shuffle(queries)
    
    successful_comments = 0
    total_posts_found = 0
    processed_urls = set()
    seo_comments_since_hobby = 0  # Track SEO comments since last hobby comment
    
    # Start with just one hobby comment
    print("\nMaking initial hobby comment...")
    make_random_hobby_comment(reddit)
    sleep_time = random.randint(60, 150)
    sleep_time = 15
    time.sleep(sleep_time)
    
    for query in queries:
        # Force hobby comment if we've made 2-3 SEO comments without one
        if seo_comments_since_hobby >= random.randint(2, 3):
            print("\nMaking a hobby comment after several SEO comments...")
            make_random_hobby_comment(reddit)
            sleep_time = random.randint(60, 150)
            time.sleep(sleep_time)
            seo_comments_since_hobby = 0  # Reset counter
        
        encoded_query = requests.utils.quote(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&tbs=qdr:w"
        
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
                        # No need for comment_variations anymore since we generate dynamically
                        if comment_on_post_by_id(reddit, post_id):
                            successful_comments += 1
                            comments_this_query += 1
                            seo_comments_since_hobby += 1
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

def get_initial_engagement_comments():
    """Return list of initial engagement comments before mentioning the tool"""
    return [
        "great insights! ",
        "really helpful post! ",
        "thanks for sharing this! ",
        "this is super useful! ",
        "great question! ",
        "interesting topic! ",
        "good points here! ",
        "thanks for bringing this up! "
    ]

def get_tool_suggestion():
    """Return list of ways to suggest the tool"""
    return [
        "btw, I've been using [keyword research tool](https://www.kwrds.ai) for this kind of stuff",
        "you might find this [SERP analysis tool](https://www.kwrds.ai) helpful",
        "check out this [people also ask tool](https://www.kwrds.ai) - helped me a lot",
        "there's this [search intent tool](https://www.kwrds.ai) that could help",
        "I use [kwrds.ai](https://www.kwrds.ai) for similar research"
    ]

# Update the main section
if __name__ == "__main__":
    print("Starting authentication process...")
    reddit = authenticate()
    
    try:
        print("\nStarting SERP processing...")
        process_serp_results(reddit)  # Remove await
        print("\nFinished all queries. Program complete.")
        
    except Exception as e:
        print(f"Error in main process: {str(e)}")


# TODO: https://www.google.com/search?q=site:reddit.com+%22keyword+research+tool%22&tbs=qdr:d
"add multiple accounts and rotate"