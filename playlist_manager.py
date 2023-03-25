import os
import random
import time
import threading
import traceback
from slack_bolt import App
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt.adapter.socket_mode import SocketModeHandler
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import ProgrammingError

import json
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from functools import partial

import logging
from slack_bolt.middleware import RequestVerification

db_lock = threading.Lock()
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] - %(message)s',
                    handlers=[logging.StreamHandler()])


# ========================================================
#  Environment Variables
# ========================================================

DB_FILE = "sqlite:///data/playlist_manager.db"
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]

WEEKLY_ID = os.environ["WEEKLY_ID"]
ARCHIVE_ID = os.environ["ARCHIVE_ID"]
SCOPE = 'playlist-modify-private'

# ========================================================
#  Spotify Authentication
# ========================================================

client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

RESULTS = sp.playlist(WEEKLY_ID)

# ========================================================
#  TODO; Slack Integration 
# ========================================================

# app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
# slack_client = WebClient(token=SLACK_BOT_TOKEN)
# handler = SocketModeHandler(app, SLACK_APP_TOKEN)

# ========================================================
#  Database Setup
# ========================================================

# Define your table classes
Base = declarative_base()

class Weekly(Base):
    __tablename__ = 'weekly'
    id = Column(String, primary_key=True)
    name = Column(String)
    album = Column(String)
    artist = Column(String)
    add_date = Column(DateTime)


class Archive(Base):
    __tablename__ = 'archive'
    id = Column(String, primary_key=True)
    name = Column(String)
    album = Column(String)
    artist = Column(String)
    add_date = Column(String)

def create_connection(database_url):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine

def create_tables(engine, database_url):
    engine = create_connection(database_url)

def execute_query(engine, query, args=None):
    with engine.connect() as connection:
        if args:
            result = connection.execute(query, args)
        else:
            result = connection.execute(query)
        rows = result.fetchall()
    return rows

logging.debug(f"starting app")

# ========================================================
#  Database Functions
# ========================================================

def insert_weekly_tracks(engine, tracks_df):
    Session = sessionmaker(bind=engine)
    session = Session()
    for _, track in tracks_df.iterrows():
        new_track = Weekly(
            id=track["id"],
            name=track["name"],
            album=track["album"],
            artist=track["artist"],
            add_date=datetime.strptime(track["add_date"], "%Y-%m-%d %H:%M")  # Convert the string to a datetime object
        )
        session.merge(new_track)
    session.commit()

def remove_weekly_track(engine, track_id):
    Session = sessionmaker(bind=engine)
    session = Session()
    track = session.query(Weekly).filter(Weekly.id == track_id).one()
    session.delete(track)
    session.commit()

def handle_old_tracks(engine, sp, weekly_playlist_id, archive_playlist_id):
    Session = sessionmaker(bind=engine)
    session = Session()

    seven_days_ago = datetime.now() + timedelta(days=1)
    # seven_days_ago = datetime.now() - timedelta(days=7)
    old_tracks = session.query(Weekly).filter(Weekly.add_date <= seven_days_ago).all()

    if old_tracks:
        print("\n---To the archive!---")
        for ot in old_tracks:
            print(ot)
            archive_track = Archive(
                id=ot.id,
                name=ot.name,
                album=ot.album,
                artist=ot.artist,
                add_date=ot.add_date
            )
            session.merge(archive_track)
            session.delete(ot)
            sp.playlist_remove_all_occurrences_of_items(weekly_playlist_id, ['spotify:track:' + ot.id])
            sp.playlist_remove_all_occurrences_of_items(archive_playlist_id, ['spotify:track:' + ot.id])
            sp.playlist_add_items(archive_playlist_id, ['spotify:track:' + ot.id])
        session.commit()
        return True
    else:
        print("No old tracks found to move to the archive.")
        return False

def get_new_songs(sp, results):
    ids = [item['track']['id'] for item in results['tracks']['items']]

    song_meta = {'id': [], 'album': [], 'name': [], 'artist': []}

    for song_id in ids:
        meta = sp.track(song_id)

        song_meta['id'].append(song_id)
        song_meta['album'].append(meta['album']['name'])
        song_meta['name'].append(meta['name'])
        song_meta['artist'].append(', '.join([singer_name['name'] for singer_name in meta['artists']]))

    tracks_df = pd.DataFrame.from_dict(song_meta)
    tracks_df['add_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")

    return tracks_df

engine = create_connection(DB_FILE)
create_tables(engine, DB_FILE)
track_df = get_new_songs(sp, RESULTS)
insert_weekly_tracks(engine, track_df)
handle_old_tracks(engine, sp, WEEKLY_ID, ARCHIVE_ID)

