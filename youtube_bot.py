from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os
import random
import time
import requests

# OAuth 2.0 credentials
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

def get_youtube_service():
    """Get authenticated YouTube service"""
    creds = None
    
    # Load saved credentials
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save credentials
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('youtube', 'v3', credentials=creds)

def get_comment_variations():
    """Return list of comment variations"""
    return [
        "great video! well done!",
        "really enjoyed this, thanks for sharing!",
        "very informative, thanks!",
        "this was super helpful!",
        "great explanation, thanks!",
        "nice work on this video!",
        "thanks for the tips!",
        "really clear explanation!"
    ]

def search_relevant_videos(youtube, query, max_results=10):
    """Search for relevant YouTube videos"""
    try:
        search_response = youtube.search().list(
            q=query,
            part='id,snippet',
            maxResults=max_results,
            type='video',
            order='date'  # Get recent videos
        ).execute()

        videos = []
        for item in search_response['items']:
            video = {
                'id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'channelTitle': item['snippet']['channelTitle'],
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            }
            videos.append(video)
        
        return videos
    except Exception as e:
        print(f"Error searching videos: {str(e)}")
        return []

def is_video_relevant(title, description):
    """Check if video is relevant to SEO/keyword research"""
    relevant_keywords = [
        'seo', 'keyword research', 'search engine optimization',
        'content strategy', 'digital marketing', 'blogging',
        'website traffic', 'google ranking'
    ]
    
    text = (title + ' ' + description).lower()
    return any(keyword in text for keyword in relevant_keywords)

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
            comment = response.json()['response'].strip()
            comment = comment.strip('"')  # Remove surrounding quotes
            comment = comment.replace('\"', '')  # Remove any remaining quotes
            return comment
        return None
    except Exception as e:
        print(f"Error generating comment: {str(e)}")
        return None

def confirm_comment(title, url, channel, comment_text):
    """Ask for confirmation before posting a comment"""
    print("\n=== Comment Confirmation ===")
    print(f"Video: {title}")
    print(f"URL: {url}")
    print(f"Channel: {channel}")
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

def post_comment(youtube, video_id, comment_text, video_info):
    """Post a comment on a YouTube video"""
    try:
        while True:  # Loop for regenerating comments
            # Generate engaging comment using LLM
            prompt = f"""Write ONE single casual YouTube comment that MUST include the exact tool name: kwrds[dot]ai

            Video Title: {video_info['title']}
            Channel: {video_info['channelTitle']}

            Rules:
            - Write exactly ONE comment
            - Keep it short (1-2 sentences)
            - Start with genuine appreciation about the video
            - MUST include exactly "kwrds[dot]ai"
            - Sound like a real person
            - Be super casual and conversational

            Example good responses:
            - "really helpful video! check out kwrds[dot]ai for similar content"
            - "great tips! i learned a lot from kwrds[dot]ai about this topic"
            - "awesome insights! btw kwrds[dot]ai has good stuff on this"
            - "super useful! reminds me of kwrds[dot]ai's approach"

            Example bad responses (don't write like this):
            - Without the exact URL
            - Multiple paragraphs
            - Formal language
            - Overly promotional tone
            """

            comment_text = generate_engaging_comment(prompt)
            if not comment_text:
                print("Failed to generate comment")
                return False

            # Ask for confirmation
            confirmed, result = confirm_comment(
                video_info['title'],
                video_info['url'],
                video_info['channelTitle'],
                comment_text
            )

            if confirmed:
                # Post the comment
                response = youtube.commentThreads().insert(
                    part='snippet',
                    body={
                        'snippet': {
                            'videoId': video_id,
                            'topLevelComment': {
                                'snippet': {
                                    'textOriginal': comment_text
                                }
                            }
                        }
                    }
                ).execute()
                return True
            elif result == "regenerate":
                continue
            else:
                return False

    except Exception as e:
        print(f"Error posting comment: {str(e)}")
        return False

def has_existing_comment(youtube, video_id):
    """Check if we've already commented on this video"""
    try:
        # Get all comments on the video
        comments = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            textFormat='plainText',
            maxResults=100  # Adjust if needed
        ).execute()
        
        # Get our channel ID for comparison
        my_channel = youtube.channels().list(
            part='id',
            mine=True
        ).execute()
        my_channel_id = my_channel['items'][0]['id']
        
        # Check each comment
        for item in comments.get('items', []):
            comment = item['snippet']['topLevelComment']
            channel_id = comment['snippet']['authorChannelId']['value']
            
            if channel_id == my_channel_id:
                print(f"Found existing comment on video {video_id}")
                return True
                
        return False
        
    except Exception as e:
        print(f"Error checking existing comments: {str(e)}")
        return True  # Safer to return True on error

def verify_comment_posted(youtube, video_id, wait_time=10):
    """Verify our comment was actually posted and not removed"""
    time.sleep(wait_time)  # Wait a bit for comment to process
    
    try:
        comments = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            textFormat='plainText',
            maxResults=100
        ).execute()
        
        my_channel = youtube.channels().list(
            part='id',
            mine=True
        ).execute()
        my_channel_id = my_channel['items'][0]['id']
        
        for item in comments.get('items', []):
            comment = item['snippet']['topLevelComment']
            channel_id = comment['snippet']['authorChannelId']['value']
            
            if channel_id == my_channel_id:
                print("Comment verification successful")
                return True
                
        print("Warning: Comment appears to have been removed")
        return False
        
    except Exception as e:
        print(f"Error verifying comment: {str(e)}")
        return False

def main():
    youtube = get_youtube_service()
    
    search_queries = [
        'SEO tutorial',
        'content strategy tips',
        'how to do keyword research',
        'keyword research tool',
        'SEO for beginners'
    ]
    
    for query in search_queries:
        print(f"\nSearching for: {query}")
        print(f"Google URL: https://www.google.com/search?q={requests.utils.quote(query)}&tbs=qdr:w")
        videos = search_relevant_videos(youtube, query)
        
        for video in videos:
            print(f"\nProcessing video: {video['title']}")
            print(f"Video URL: {video['url']}")
            
            # Check for existing comment first
            if has_existing_comment(youtube, video['id']):
                print("Skipping: Already commented on this video")
                continue
            
            # Generate and preview comment
            print("\nGenerating Comment...")
            if post_comment(youtube, video['id'], None, video):
                print(f"Comment posted successfully on: {video['url']}")
                # time.sleep(5)
                if verify_comment_posted(youtube, video['id']):
                    print("Comment verified - still visible after delay")
                else:
                    print("Warning: Comment may have been removed by YouTube")
                # time.sleep(5)
            else:
                print("Skipping this video")
                
            # time.sleep(5)

if __name__ == '__main__':
    main() 