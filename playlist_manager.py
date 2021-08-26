import json
import sqlite3
import spotipy
import datetime
import pandas as pd
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy.util as util
import config

username = config.USERNAME
client_id = config.CLIENT_ID #insert your client id
client_secret = config.CLIENT_SECRET # insert your client secret id here
redirect_uri = 'http://127.0.0.1:8080'
scope = 'playlist-modify-private'

token = util.prompt_for_user_token(username, scope, client_id, client_secret, redirect_uri)
# client_credentials_manager = SpotifyClientCredentials(client_id, client_secret, redirect_uri)

sp = spotipy.Spotify(auth=token)

weekly_playlist_id='4KVjL7J08ftGgKUtC4XGYX' #insert your playlist id
archive_playlist_id='1tYeMCFbT3Mllhwy6DSi3m'
results = sp.playlist(weekly_playlist_id)

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

    conn = create_connection('database/playlist.db')

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

    conn = create_connection('database/playlist.db')
    
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
    
    conn = create_connection('database/playlist.db')

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

    conn = create_connection('database/playlist.db')

    select_sql = ''' SELECT id, name, album, artist, add_date
                        FROM weekly
                        WHERE add_date < (SELECT datetime('now','-7 days'));
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

        conn = create_connection('database/playlist.db')

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

