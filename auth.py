import os
import time
import requests
from urllib.parse import urlencode

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REDIRECT_URI = os.environ["REDIRECT_URI"]
SCOPE = 'playlist-modify-private'

# User Authorization: Step 1 - Generate the authorization URL
auth_url = "https://accounts.spotify.com/authorize"
params = {
    "client_id": CLIENT_ID,
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
}
auth_url = f"{auth_url}?{urlencode(params)}"
print(f"URL: {auth_url}")

# User Authorization: Step 2 - User logs in and authorizes the app
print("Please visit the following URL to authorize the app: \n")
print(auth_url)
auth_code = input("\nEnter the code received from the URL above: ")

# Token Exchange: Step 1 - Exchange the authorization code for an access token
token_url = "https://accounts.spotify.com/api/token"
payload = {
    "grant_type": "authorization_code",
    "code": auth_code,
    "redirect_uri": REDIRECT_URI,
}

response = requests.post(token_url, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
print(f"Response status: {response.status_code}")

if response.status_code == 200:
    token_data = response.json()
    access_token = token_data["access_token"]
    print(f"Access token: {access_token}")
else:
    print("Error: Unable to obtain access token.")
