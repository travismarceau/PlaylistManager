import os
import random
import time
import threading
import traceback
from slack_bolt import App
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt.adapter.socket_mode import SocketModeHandler
from sqlalchemy import create_engine, MetaData, Table, Column, String, Float, text, Integer

import json
import sqlite3
import spotipy
import datetime
import pandas as pd
from spotipy.oauth2 import SpotifyOAuth
import spotipy.util as util

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

DB_FILE = os.environ["DATABASE_URL"]
USERNAME = os.environ["USERNAME"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]

WEEKLY_ID = os.environ["WEEKLY_ID"]
ARCHIVE_ID = os.environ["ARCHIVE_ID"]
SCOPE = 'playlist-modify-private'

# ========================================================
#  Spotify Authentication
# ========================================================

redirect_uri = 'playlistmanager-production.up.railway.app/callback'

from spotipy.oauth2 import SpotifyOAuth

sp_oauth = SpotifyOAuth(CLIENT_ID, CLIENT_SECRET, redirect_uri, scope=SCOPE, username=USERNAME)
token_info = sp_oauth.get_cached_token()

if not token_info:
    auth_url = sp_oauth.get_authorize_url()
    print(f"Please navigate here: {auth_url}")
    print("After you authorize the app, copy the code and run the following command:")
    print(f"heroku config:set SPOTIPY_AUTH_CODE=<paste_the_code_here> -a your-heroku-app-name")

token = token_info['access_token']
sp = spotipy.Spotify(auth=token)

RESULTS = sp.playlist(weekly_playlist_id)

# ========================================================
#  TODO; Slack Integration 
# ========================================================

# app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
# slack_client = WebClient(token=SLACK_BOT_TOKEN)
# handler = SocketModeHandler(app, SLACK_APP_TOKEN)

# ========================================================
#  Database Setup
# ========================================================

engine = create_engine(DATABASE_URL)
metadata = MetaData()

tasks = Table('tasks', metadata,
              Column('id', Integer, primary_key=True, autoincrement=True),
              Column('user_id', String),
              Column('task_name', String),
              Column('channel_id', String),
              Column('start_time', Float),
              Column('end_time', Float),
              Column('status', String)
              )


metadata.create_all(engine)

def execute_query(query, params=None):
    with engine.connect() as conn:
        if params:
            logging.debug(f"===QUERY==={query} {params}")
            result = conn.execute(text(query), params)
        else:
            result = conn.execute(text(query))
        return result.fetchall()


def execute_commit(query, params=None):
    with engine.connect() as conn:
        try:
            with conn.begin():
                if params:
                    logging.debug(f"===QUERY==={query} {params}")
                    logging.debug(conn.execute(text(query), params))
                else:
                    conn.execute(text(query))
        except Exception as e:
            logging.error(f"An error occurred while executing the transaction: {e}")
            logging.error(traceback.format_exc())


logging.debug(f"starting app")

# ========================================================
#  Database Functions
# ========================================================

def create_connection(db_file):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        # print(sqlite3.version)
        conn = sqlite3.connect(db_file,detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    except sqlite3.Error as e:
        print(e)

    return conn

def no_args_query(conn, the_sql):
    """ run query - no args - no return """
    try:
        c = conn.cursor()
        c.execute(the_sql)
        conn.commit()
    except sqlite3.Error as e:
        print(e)
    finally:
        conn.close()

def args_query(conn, the_sql, args):
    """ run query - with args - no return """
    try:
        c = conn.cursor()
        c.execute(the_sql, args)
        conn.commit()
    except sqlite3.Error as e:
        print(e)
    finally:
        conn.close()

def select_query(conn, the_sql):
    """ select and return statement - no args """
    rows = None
    try:
        c = conn.cursor()
        c.execute(the_sql)
        rows = c.fetchall()
        c.close()
    except sqlite3.Error as e:
        print(e)
        return
    finally:
        conn.close()
        return rows

def create_db(create_sql):

    conn = create_connection(database_file)

    if conn is not None:
        # create projects table
        no_args_query(conn, create_sql)
        return True

    else:
        print("Error! cannot create the database connection.")
        return False

def create_tables():

    create_weekly = '''CREATE TABLE IF NOT EXISTS weekly (
                            id text PRIMARY KEY NOT NULL,
                            name text,
                            album text,
                            artist text,
                            add_date text);
                            '''

    create_archive = '''CREATE TABLE IF NOT EXISTS archive (
                            id text PRIMARY KEY NOT NULL,
                            name text,
                            album text,
                            artist text,
                            add_date text);
                            '''

    create_db(create_weekly)
    create_db(create_archive)

def insert_weekly_tracks(tracks_df):

    conn = create_connection(database_file)
    
    if conn is not None:
        query=''' INSERT OR IGNORE INTO weekly 
                    (id, name, album, artist, add_date) 
                    VALUES (?,?,?,?,?); '''
        conn.executemany(query, tracks_df.to_records(index=False))
        conn.commit()
        return True

    else:
        print("Error! cannot create the database connection.")
        return False

def remove_weekly_track(track_id):
    
    conn = create_connection(database_file)

    insert_sql = ''' DELETE FROM weekly
                        WHERE id = ?;
                '''
    if conn is not None:
        args_query(conn, insert_sql, track_id)
        return True

    else:
        print("Error! cannot create the database connection.")
        return False

def handle_old_tracks():

    conn = create_connection(database_file)

    select_sql = ''' SELECT id, name, album, artist, add_date
                        FROM weekly
                        WHERE add_date <= (SELECT datetime('now','-7 days'));
                '''

    tracks = []
    json_tracks = []
    if conn is not None:
        rows = select_query(conn, select_sql)
        if(rows):
            print("\n---To the archive!---")
            for ot in rows:
                print(ot)
                tracks.append([ot[0]])
                json_tracks.append('spotify:track:'+ot[0])
                # insert_archive_track(ot)
    
    else:
        print("Error! cannot create the database connection.")
        return False
    
    if(tracks):

        conn = create_connection(database_file)

        print(rows)
        print("\n\n",tracks)

        if conn is not None:
            query=''' INSERT OR REPLACE INTO archive 
                        (id, name, album, artist, add_date) 
                        VALUES (?,?,?,?,?); '''
            conn.executemany(query, rows)

            delete_sql = ''' DELETE FROM weekly
                        WHERE id = ?; '''
            conn.executemany(delete_sql, tracks)
            conn.commit()

            sp.playlist_remove_all_occurrences_of_items(weekly_playlist_id, json_tracks)
            sp.playlist_remove_all_occurrences_of_items(archive_playlist_id, json_tracks)
            sp.playlist_add_items(archive_playlist_id, json_tracks)
            return True

        else:
            print("Error! cannot create the database connection.")
            return False

        

def get_new_songs():
    # create a list of song ids
    ids=[]

    for item in results['tracks']['items']:
            track = item['track']['id']
            ids.append(track)
            
    song_meta={'id':[],'album':[], 'name':[], 
            'artist':[]}

    for song_id in ids:
        # get song's meta data
        meta = sp.track(song_id)
        
        # song id
        song_meta['id'].append(song_id)

        # album name
        album=meta['album']['name']
        song_meta['album']+=[album]

        # song name
        song=meta['name']
        song_meta['name']+=[song]
        
        # artists name
        s = ', '
        artist=s.join([singer_name['name'] for singer_name in meta['artists']])
        song_meta['artist']+=[artist]

        # # date added
        # song

    tracks_df=pd.DataFrame.from_dict(song_meta)
    tracks_df['add_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # with pd.option_context('display.max_rows', None, 'display.max_columns', None):
    #     print(tracks_df)

    return tracks_df

create_tables()
track_df = get_new_songs()
insert_weekly_tracks(track_df)
handle_old_tracks()

