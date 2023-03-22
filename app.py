from flask import Flask, request, redirect
import spotipy
from spotipy.oauth2 import SpotifyOAuth

app = Flask(__name__)

@app.route('/callback')
def callback():
    sp_oauth = SpotifyOAuth()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    return redirect(f'/token/{token_info["access_token"]}/{token_info["refresh_token"]}')

if __name__ == "__main__":
    app.run(debug=True, port=8080)