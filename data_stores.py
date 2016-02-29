"""
Classes to abstract storing user data in different stores, e.g. local file, mongodb, or S3 bucket.

@jonathanronen 2016/2
"""

import os
import gzip
import tinys3
from io import BytesIO
from bson import json_util as json

class LocalStore:
    def __init__(self, directory):
        self.dir = directory

    def store_object(self, key, data):
        filename = os.path.join(self.dir, key+'.json.gz')
        i = 1
        while os.path.isfile(filename):
            filename = os.path.join(self.dir, key + '.' + str(i) + '.json.gz')
            i += 1

        with gzip.open(filename, 'wt') as outfile:
            outfile.write(json.dumps(data))

class S3Store:
    def __init__(self, access_key, secret_key, **kwargs):
        self.conn = tinys3.Connection(access_key, secret_key, **kwargs)

    def store_object(self, key, data):
        byte_buffer = BytesIO()
        with gzip.GzipFile(fileobj=byte_buffer, mode='w') as f:
            f.write(json.dumps(data))
        byte_buffer.seek(0)
        conn.upload(key, byte_buffer)

