"""
This script downloads "deep" user data - including likes and comments.
To be run as an extra step, to download data again later, or if something's gone wrong. The main way to download the data is the `background_crawler.py` script.

It assumes the users data is in a mongodb database with an address configurable at runtime.
The MongoDB database has a collection named `users`, where user objects look like this:

    {
        "_id" : ObjectId("xxx"),
        "timestamp" : ISODate("xxxx-xx-xx xx:xx:xx"),
        "respondent_id" : "1234",
        "token" : {
                "access_token" : "xxx",
                "expires" : "1234"
        },
        "user" : {
                "name" : "name of facebook profile",
                "id" : "application specific id of that user"
        },
        "permissions" : {
                "data" : [
                        {
                                "status" : "granted",
                                "permission" : "user_religion_politics"
                        },
                        {
                                "status" : "granted",
                                "permission" : "user_likes"
                        },
                        {
                                "status" : "granted",
                                "permission" : "user_posts"
                        },
                        {
                                "status" : "granted",
                                "permission" : "user_actions.news"
                        },
                        {
                                "status" : "granted",
                                "permission" : "public_profile"
                        }
                ]
        }
    }

Each user is saved as a xxxxxxxx.json.gz file in OUTPUT_DIR, where xxxxxxx is that user's application specific user id on facebook.
Users that have already been downloaded with this script, for whom a the file user_id.json.gz already exists in OUTPUT_DIR, will not be re-downloaded.

-------------------------------------

Usage:
    get_user_data_with_comments_likes.py [-h] [--database-ip DATABASE_IP]
                                                [--database-port DATABASE_PORT]
                                                [--database-username DATABASE_USERNAME]
                                                [--database-password DATABASE_PASSWORD]
                                                [--database-dbname DATABASE_DBNAME]
                                                [--users-from USERS_FROM]
                                                [--users-until USERS_UNTIL]
                                                [--concurrent-users-processes CONCURRENT_USERS_PROCESSES]
                                                [--concurrent-requests-threads CONCURRENT_REQUESTS_THREADS]
                                                [--output-dir OUTPUT_DIR]

    optional arguments:
      -h, --help            show this help message and exit
      --database-ip DATABASE_IP
      --database-port DATABASE_PORT
      --database-username DATABASE_USERNAME
      --database-password DATABASE_PASSWORD
      --database-dbname DATABASE_DBNAME
      --users-from USERS_FROM
                            If present, only download users who signed up after
                            this timestamp 'YEAR-MONTH-DAY HH:MM:SS'
      --users-until USERS_UNTIL
                            If present, only download users who signed up before
                            this timestamp 'YEAR-MONTH-DAY HH:MM:SS'
      --concurrent-users-processes CONCURRENT_USERS_PROCESSES
                            Number of users to download concurrently [3]
      --concurrent-requests-threads CONCURRENT_REQUESTS_THREADS
                            Number of threads per user [2]
      --output-dir OUTPUT_DIR


@jonathanronen 2016/12
"""

import os
import gzip
import argparse
import facebook
import requests
from time import time, sleep
from datetime import datetime
from functools import partial
from pymongo import MongoClient
from multiprocessing import Pool
from bson import json_util as json
from bson import decode_all, ObjectId
from multiprocessing.pool import ThreadPool

from smappPy.smapp_logging import logging
logger = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.WARNING)
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

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

def write_data(data, dirname='.'):
    key = data['profile']['id']
    filename = os.path.join(dirname, key+'.json.gz')
    i = 1
    while os.path.isfile(filename):
        filename = os.path.join(dirname, key + '.' + str(i) + '.json.gz')
        i += 1

    with gzip.open(filename, 'wt') as outfile:
        outfile.write(json.dumps(data))

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

def get_mongo_collection(server, port, username, password, dbname, colname):
    cl = MongoClient(server, port)
    db = cl[dbname]
    if username and password:
        db.authenticate(username, password)
    return db[colname]

def get_users_queue(db_host, db_port, db_username, db_password, db_name, from_datetime, until_datetime):
    col = get_mongo_collection(db_host, db_port, db_username, db_password, db_name, 'users')
    users = list(col.find({'timestamp': {'$gte': from_datetime, '$lte': until_datetime}, 'permissions': {'$ne': 'DENIED'}}))
    return users

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-ip', default='localhost')
    parser.add_argument('--database-port', default=27017, type=int)
    parser.add_argument('--database-username')
    parser.add_argument('--database-password',)
    parser.add_argument('--database-dbname', default='smapp_anes_fb')
    parser.add_argument('--users-from', default='2016-11-1 00:00:00', help=r"If present, only download users who signed up after this timestamp 'YEAR-MONTH-DAY HH:MM:SS' [datetime.min]")
    parser.add_argument('--users-until', help=r"If present, only download users who signed up before this timestamp 'YEAR-MONTH-DAY HH:MM:SS' [datetime.max]")
    parser.add_argument('--concurrent-users-processes', default=3, type=int, help="Number of users to download concurrently [3]")
    parser.add_argument('--concurrent-requests-threads', default=2, type=int, help="Number of threads per user [2]")
    parser.add_argument('--output-dir', default='.')
    args = parser.parse_args()

    users_still_valid = [1,2,3] # this is a placeholder
    while len(users_still_valid)>0:
        try:
            logger.info("Getting users..")
            from_datetime = datetime.strptime(args.users_from, '%Y-%m-%d %H:%M:%S') if args.users_from else datetime.min
            until_datetime = datetime.strptime(args.users_until, '%Y-%m-%d %H:%M:%S') if args.users_until else datetime.max
            users = get_users_queue(args.database_ip, args.database_port, args.database_username, args.database_password, args.database_dbname,
                                    from_datetime, until_datetime)
            logger.info("Have {} users.".format(len(users)))
            
            unique_user_ids = set()
            unique_users = list()
            for user in users:
                if user['user']['id'] not in unique_user_ids:
                    unique_user_ids.add(user['user']['id'])
                    unique_users.append(user)
            logger.info("({} unique)".format(len(unique_users)))

            # look for users already downloaded..
            already_downloaded_ids = { f.split('.json')[0] for f in os.listdir(args.output_dir) if f.endswith('.json.gz') }
            logger.info("Already downloaded {} users".format(len(already_downloaded_ids)))
            remaining_users = list()
            for user in unique_users:
                if user['user']['id'] not in already_downloaded_ids:
                    remaining_users.append(user)
            logger.info("({} remain)".format(len(remaining_users)))
            
            # validate token still valid
            users_still_valid = list()
            invalids = 0
            for user in remaining_users:
                try:
                    g = facebook.GraphAPI(user['token']['access_token'])
                    g.get_object('me')
                    users_still_valid.append(user)
                except:
                    invalids += 1
            logger.info("{} still have valid tokens ({} invalid)".format(len(users_still_valid), invalids))

            # start threads
            def do_one(user):
                return do_one_user(user, args.concurrent_requests_threads)
            pool = Pool(args.concurrent_users_processes)
            done = 0
            start_time = time()
            for user_data in pool.imap_unordered(do_one, users_still_valid):
                done += 1
                write_data(user_data, args.output_dir)
                elapsed = time() - start_time
                ups = done / elapsed
                remain = (len(users_still_valid)-done) / ups
                logger.info("Finished {} users in {:.2f}s (approx. {:.2f}s remain)".format(done, elapsed, remain))
            pool.close()
            pool.join()
            logger.info("Done! Bye.")
        except Exception as e:
            pool.terminate()
            logger.info(str(e))
            logger.info("Sleeping for 1 hour")
            sleep(3600)