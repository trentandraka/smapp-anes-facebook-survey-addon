import os
import yaml
import facebook
from flask import Flask
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask import render_template, url_for, request, redirect


app = Flask(__name__)
this_path = os.path.dirname(os.path.realpath(__file__))
SETTINGS = yaml.load(open(os.path.join(this_path, 'settings.yml')))
PERMISSIONS = ','.join(SETTINGS['facebook']['permissions'])



FACEBOOK_LINK = "https://www.facebook.com/dialog/oauth?response_type=token&client_id={app_id}&redirect_uri={callback}&scope={scope}"
@app.route('/')
def welcome():
    facebook_link = FACEBOOK_LINK.format(
        app_id=SETTINGS['facebook']['app_id'],
        callback=SETTINGS['url'] + url_for('callback_from_fb'),
        scope=PERMISSIONS)
    print facebook_link
    return render_template('welcome.html', facebook_link=facebook_link)

@app.route('/callback')
def callback_from_fb():
    return render_template('callback.html')

@app.route('/token')
def token():
    token = request.args['fragment']
    g = facebook.GraphAPI(token)
    res = g.extend_access_token(SETTINGS['facebook']['app_id'], SETTINGS['facebook']['app_secret'])
    res['expires_date'] = datetime.now() + timedelta(seconds=int(res['expires']))
    user = g.get_object("me")
    permissions = g.get_object("me/permissions")
    db = get_db_connection()
    db.users.save({
        "user": user,
        "token": res,
        "permissions": permissions
        })
    return redirect(url_for('thanks', userid=user['id']))

@app.route('/thanks/<userid>')
def thanks(userid):
    name = get_db_connection().users.find_one({'user.id': userid})['user']['name']
    return render_template("thanks.html", name=name)


def get_db_connection():
    cl = MongoClient(SETTINGS['database']['host'], SETTINGS['database']['port'])
    db = cl[SETTINGS['database']['db']]
    if SETTINGS['database']['username'] and SETTINGS['database']['password']:
        db.authenticate(SETTINGS['database']['username'], SETTINGS['database']['password'])
    return db

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

