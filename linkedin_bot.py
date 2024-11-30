import requests
import json
import os
from dotenv import load_dotenv
import webbrowser
from urllib.parse import urlencode

load_dotenv()

class LinkedInBot:
    def __init__(self):
        self.client_id = os.getenv('LINKEDIN_CLIENT_ID')
        self.client_secret = os.getenv('LINKEDIN_CLIENT_SECRET')
        self.redirect_uri = "http://localhost:3000"
        self.access_token = os.getenv('LINKEDIN_ACCESS_TOKEN')
        self.org_id = os.getenv('LINKEDIN_ORG_ID')
        
        if not self.access_token:
            self.get_access_token()

    def get_authorization_url(self):
        """Generate LinkedIn OAuth2 authorization URL"""
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'r_liteprofile r_emailaddress w_member_social',
            'state': 'random_state_string'
        }
        
        auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"
        print("\nDebug: Authorization parameters:")
        print(f"Client ID: {self.client_id}")
        print(f"Redirect URI: {self.redirect_uri}")
        print(f"Full Auth URL: {auth_url}")
        return auth_url

    def get_access_token(self):
        """Get OAuth2 access token"""
        auth_url = self.get_authorization_url()
        print("\nPlease visit this URL to authorize the application:")
        print(auth_url)
        webbrowser.open(auth_url)
        
        print("\nAfter authorizing, you'll be redirected to a URL like:")
        print(f"{self.redirect_uri}?code=YOUR_AUTH_CODE&state=random_state_string")
        auth_code = input("\nEnter ONLY the code parameter value from the URL: ")
        
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri
        }
        
        print("\nDebug: Token request data:")
        print(json.dumps(data, indent=2))
        
        response = requests.post(token_url, data=data)
        print(f"\nDebug: Token response status: {response.status_code}")
        print(f"Debug: Token response headers: {dict(response.headers)}")
        print(f"Debug: Token response body: {response.text}")
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data['access_token']
            print("\nSuccessfully obtained access token!")
            print("Add this to your .env file:")
            print(f"LINKEDIN_ACCESS_TOKEN={self.access_token}")
        else:
            print(f"\nFailed to get access token: {response.text}")
            raise Exception("Authentication failed")

    def create_comment(self, post_urn: str, comment_text: str) -> bool:
        """Create a comment on a LinkedIn post using the Comments API"""
        try:
            url = f"https://api.linkedin.com/v2/socialActions/{post_urn}/comments"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'X-Restli-Protocol-Version': '2.0.0',
                'LinkedIn-Version': '202401'
            }
            
            data = {
                "actor": f"urn:li:organization:{self.org_id}",
                "message": {
                    "text": comment_text
                }
            }
            
            print(f"\nAttempting to comment on post: {post_urn}")
            print(f"Comment text: {comment_text}")
            print(f"Headers: {json.dumps(headers, indent=2)}")
            print(f"Data: {json.dumps(data, indent=2)}")
            
            response = requests.post(
                url,
                headers=headers,
                json=data
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text[:500]}")
            
            if response.status_code in [200, 201]:
                print("Comment posted successfully!")
                return True
            else:
                print(f"Failed to post comment. Status code: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error details: {json.dumps(error_data, indent=2)}")
                except:
                    pass
                return False
                
        except Exception as e:
            print(f"Error posting comment: {str(e)}")
            return False

def test_comment():
    bot = LinkedInBot()
    post_urn = "urn:li:activity:7267886989482307585"
    comment = "Great work!"
    
    success = bot.create_comment(post_urn, comment)
    if success:
        print("Test comment successful!")
    else:
        print("Test comment failed.")

if __name__ == "__main__":
    test_comment() 