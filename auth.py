import os
import time
import requests

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REDIRECT_URI = os.environ["REDIRECT_URI"]

# Device Flow: Step 1 - Get the device code
auth_url = f"https://accounts.spotify.com/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope={SCOPE}"
print(f"URL: {auth_url}")

response = requests.get(auth_url)
print("Response content:", response.content)

response_data = response.json()

# auth_url = "https://accounts.spotify.com/api/device_authorization"
# payload = {
#     "client_id": CLIENT_ID,
#     "scope": "playlist-modify-private",
# }

# response = requests.post(auth_url, data=payload)
print(f"Response status: {response.status_code}")
print(f"Response content: {response.content}")
response_data = response.json()

device_code = response_data["device_code"]
user_code = response_data["user_code"]
verification_uri = response_data["verification_uri"]
verification_uri_complete = response_data["verification_uri_complete"]
expires_in = response_data["expires_in"]
interval = response_data["interval"]

print(f"Please visit the following URL to authorize the app: {verification_uri_complete}")

# Device Flow: Step 2 - Poll for the access token
token_url = "https://accounts.spotify.com/api/token"
start_time = time.time()

while True:
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": CLIENT_ID,
        "device_code": device_code,
    }

    response = requests.post(token_url, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    print(f"Response status: {response.status_code}")
    print(f"Response content: {response.content}")

    response_data = response.json()

    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data["access_token"]
        print(f"Access token: {access_token}")
        break
    elif response.status_code == 400 and time.time() < start_time + expires_in:
        time.sleep(interval)
    else:
        print("Error: Unable to obtain access token.")
        break
