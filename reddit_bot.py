import praw
import os
import pickle
from prawcore.exceptions import OAuthException

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

def comment_on_post_by_id(reddit, post_id, comment_text):
    try:
        submission = reddit.submission(id=post_id)
        submission.reply(comment_text)
        print(f"Successfully commented on post: {submission.title}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

# Example usage
if __name__ == "__main__":
    print("Starting authentication process...")
    reddit = authenticate()
    
    # The ID of the post you want to comment on
    post_id = "1es3jf2"
    comment_text = "[kwrds.ai](https://www.kwrds.ai) is a great keyword research tool with a great SERP analysis tool and people also ask and people also search for features"
    
    # Comment on the post
    comment_on_post_by_id(reddit, post_id, comment_text) 


# TODO: https://www.google.com/search?q=site:reddit.com+%22keyword+research+tool%22&tbs=qdr:d
"this grabs query by day etc. Need to make this a cron job spammer every day"
"need to create multiple reddit accounts and rotate them to not be banned."