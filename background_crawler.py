"""
This script runs in the background next to the webapp. It periodically checks the "users" table in the database, and if a new user
had been added, downloads all of that user's data.

Also downloads posts' likes and comments.

Enables concurrent downloading of posts via the --concurrent-request-threads argument

Usage:
    python background_crawler.py

@jonathanronen 2017/3
"""

import os
import yaml
import argparse
import facebook
import requests
import data_stores
from bson import ObjectId
from time import sleep, time
from datetime import datetime
from functools import partial
from pymongo import MongoClient
from multiprocessing.pool import ThreadPool

from smappPy.smapp_logging import logging
logger = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.WARNING)

default_settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smapp_facebook_signon', 'settings.yml')

def get_mongo_collection(server, port, username, password, dbname, colname):
    cl = MongoClient(server, port)
    db = cl[dbname]
    if username and password:
        db.authenticate(username, password)
    return db[colname]

def get_users_queue(db_host, db_port, db_username, db_password, db_name):
    col = get_mongo_collection(db_host, db_port, db_username, db_password, db_name, 'users')
    users = list(col.find({'downloaded': {'$exists': False}, 'exception': {'$exists': False}}))
    return users

def set_user_updated(db_host, db_port, db_username, db_password, db_name, user_id):
    col = get_mongo_collection(db_host, db_port, db_username, db_password, db_name, 'users')
    r = col.update_one({'_id': ObjectId(user_id)}, { '$set': {'downloaded': datetime.now()} } )

def update_user_with_exception(db_host, db_port, db_username, db_password, db_name, user_id, ex):
    col = get_mongo_collection(db_host, db_port, db_username, db_password, db_name, 'users')
    r = col.update_one({'_id': ObjectId(user_id)}, { '$set': { 'exception': str(ex) } } )

def download_with_paging(resp):
    all_data = resp.get('data', [])
    try:
        while 'next' in resp.get('paging', {}) and len(resp.get('data',[])) > 0:
            resp = requests.get(resp['paging']['next']).json()
            all_data += resp.get('data', [])
    except Exception as e:
        return e
    return all_data

comment_fields = ['id','attachment','comment_count','created_time','from','like_count','message','message_tags','object','parent']
def fill_post(post, g):
    try:
        post['comments'] = download_with_paging(g.get_connections(post['id'], 'comments', fields=comment_fields))
        for comment in post['comments']:
            if comment['like_count']>0:
                try:
                    comment['likes'] = download_with_paging(g.get_connections(comment['id'], 'likes'))
                except Exception as e:
                    comment['likes'] = str(e)
    except Exception as eo:
        post['comments'] = str(eo)
    try:
        post['likes'] = download_with_paging(g.get_connections(post['id'], 'likes'))
    except Exception as eo:
        post['likes'] = str(eo)
    try:
        post_fields = ['id','admin_creator','application','call_to_action','caption','created_time','description','feed_targeting','from','icon','instagram_eligibility','is_hidden','is_instagram_eligible','is_published','link','message','message_tags','name','object_id','parent_id','permalink_url','picture','place','privacy','properties','shares','source','status_type','story','story_tags','targeting','to','type','updated_time','with_tags',]
        post['sharedposts'] = download_with_paging(g.get_connections(post['id'], 'sharedposts', fields=post_fields))
    except Exception as eo:
        post['sharedposts'] = str(eo)
    return post

def do_one_user(user, n_threads=2):
    user_data = dict()
    user_data['respondent_id'] = user['respondent_id']
    g = facebook.GraphAPI(user['token']['access_token'])
    mymeta = g.get_object('me', metadata=1)
    fields = [f['name'] for f in mymeta['metadata']['fields']]
    nonbusiness_fields = [e for e in fields if 'business' not in e and 'employee' not in e]
    other_banned_fields = {'age_range', 'admin_notes', 'labels'}
    fields_to_ask = [str(e) for e in list(set(nonbusiness_fields) - other_banned_fields)]
    profile = g.get_object('me', fields=fields_to_ask)
    user_data['profile'] = profile
    post_fields = ['id','admin_creator','application','call_to_action','caption','created_time','description','feed_targeting','from','icon','instagram_eligibility','is_hidden','is_instagram_eligible','is_published','link','message','message_tags','name','object_id','parent_id','permalink_url','picture','place','privacy','properties','shares','source','status_type','story','story_tags','targeting','to','type','updated_time','with_tags',]
    feed = download_with_paging(g.get_connections('me', 'feed', fields=post_fields))
    tp = ThreadPool(n_threads)
    feed_filled = tp.map(partial(fill_post, g=g), feed)
    tp.close()
    tp.join()
    user_data['feed'] = feed
    return user_data

def download_data_for_user(user, data_store, n_threads):
    try:
        logger.info("downloading data for user {} into data store.".format(user['user']['id']))
        user_data = do_one_user(user, n_threads)
        logger.info("downloaded. storing.")
        data_store.store_object(user['user']['id'], user_data)
        logger.info("Stored user data")

        return True, None
    except Exception as e:
        return False, e


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config-file", default=default_settings_path,
        help="Path to config file [smapp_facebok_signon/settings.yml]")
    parser.add_argument('--concurrent-requests-threads', default=2, type=int, help="Number of threads per user [2]")
    parser.add_argument("-s", "--sleep-time", default=300, type=int,
        help="Time (in seconds) to wait before checking queue [300]")
    args = parser.parse_args()

    with open(args.config_file, 'rt') as infile:
        SETTINGS = yaml.load(infile)

    logger.info("Hi.")
    logger.info("Queue is at {server}:{port}/{db}/{col}".format(
        server=SETTINGS['database']['host'],
        port=SETTINGS['database']['port'],
        db=SETTINGS['database']['db'],
        col='users'
        ))
    
    logger.info("Data store is {}".format(
        SETTINGS['data_store']['store_class']))
    data_store = getattr(data_stores, SETTINGS['data_store']['store_class'])(**SETTINGS['data_store']['store_params'])

    users_queue = get_users_queue(
        SETTINGS['database']['host'],
        SETTINGS['database']['port'],
        SETTINGS['database']['username'],
        SETTINGS['database']['password'],
        SETTINGS['database']['db'],
        )

    while True:
        while len(users_queue) > 0:
            if 'user' in users_queue[0]:
                logger.info(u"Downloading data for {name} ({id})".format(
                    name=users_queue[0]['user']['name'],
                    id=users_queue[0]['user']['id']))
                u = users_queue.pop(0)
                ok, ex = download_data_for_user(u, data_store, args.concurrent_requests_threads)
                if ok:
                    logger.info("Data stored succesfully.")
                    set_user_updated(
                        SETTINGS['database']['host'],
                        SETTINGS['database']['port'],
                        SETTINGS['database']['username'],
                        SETTINGS['database']['password'],
                        SETTINGS['database']['db'],
                        u['_id']
                        )
                    logger.info("User marked as downloaded in DB")
                else:
                    logger.warn("Got an exception.")
                    logger.warn(ex)
                    update_user_with_exception(
                        SETTINGS['database']['host'],
                        SETTINGS['database']['port'],
                        SETTINGS['database']['username'],
                        SETTINGS['database']['password'],
                        SETTINGS['database']['db'],
                        u['_id'],
                        ex
                        )
                    logger.warn("Marked user {} with exception in DB".format(u['user']['id']))
            else:
                u = users_queue.pop(0)
                logger.info("NO 'user' in {}".format(u))
                set_user_updated(
                    SETTINGS['database']['host'],
                    SETTINGS['database']['port'],
                    SETTINGS['database']['username'],
                    SETTINGS['database']['password'],
                    SETTINGS['database']['db'],
                    u['_id']
                    )
                logger.info("Marked in DB.")
        while len(users_queue) == 0:
            logger.info("Sleeping for {} seconds before re-checking if there's work to do".format(args.sleep_time))
            sleep(args.sleep_time)
            users_queue = get_users_queue(
                SETTINGS['database']['host'],
                SETTINGS['database']['port'],
                SETTINGS['database']['username'],
                SETTINGS['database']['password'],
                SETTINGS['database']['db'],
                )

