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

ROUTE_PREFIX = SETTINGS['app-prefix']

FACEBOOK_LINK = "https://www.facebook.com/dialog/oauth?response_type=token&client_id={app_id}&redirect_uri={callback}&scope={scope}"
@app.route(ROUTE_PREFIX + '/')
def welcome():
    return render_template('welcome.html')

@app.route(ROUTE_PREFIX + '/gotofacebook')
def gotofacebook():
    respondent_id = request.args.get('respondent_id', 'NA')
    if respondent_id == ' ':
        respondent_id = 'NA'
        return render_template('welcome_please_fill.html')
    facebook_link = FACEBOOK_LINK.format(
        app_id=SETTINGS['facebook']['app_id'],
        callback=SETTINGS['url'] + url_for('callback_with_id', respondent_id=respondent_id),
        scope=PERMISSIONS)
    return render_template('gotofb.html', facebook_link=facebook_link)

@app.route(ROUTE_PREFIX + '/welcome/<respondent_id>')
def welcome_with_id(respondent_id):
    return render_template('welcome.html', respondent_id=respondent_id)

@app.route(ROUTE_PREFIX + '/callback/<respondent_id>')
def callback_with_id(respondent_id):
    if 'error' in request.args: # user denied
        db = get_db_connection()
        db.users.insert_one({
        "respondent_id": respondent_id,
        "permissions": "DENIED",
        "timestamp": datetime.now(),
        "error": request.args
        })
    return render_template('callback_with_id.html', respondent_id=respondent_id)

@app.route(ROUTE_PREFIX + '/callback')
def callback_from_fb():
    return render_template('callback.html')

@app.route(ROUTE_PREFIX + '/token')
def token():
    respondent_id = request.args.get('respondent_id', 'NA')
    token = request.args['fragment']
    if token == '_': # user denied
        db = get_db_connection()
        db.users.insert_one({
        "respondent_id": respondent_id,
        "permissions": "DENIED",
        "timestamp": datetime.now()
        })
        return redirect(url_for('thanks_for_nothing'))
    g = facebook.GraphAPI(token)
    res = g.extend_access_token(SETTINGS['facebook']['app_id'], SETTINGS['facebook']['app_secret'])
    user = g.get_object("me")
    permissions = g.get_object("me/permissions")
    db = get_db_connection()
    db.users.insert_one({
        "respondent_id": respondent_id,
        "user": user,
        "token": res,
        "permissions": permissions,
        "timestamp": datetime.now()
        })
    return redirect(url_for('thanks', userid=user['id']))

@app.route(ROUTE_PREFIX + '/thanks/<userid>')
def thanks(userid):
    name = get_db_connection().users.find_one({'user.id': userid})['user']['name']
    return render_template("thanks.html", name=name)

@app.route(ROUTE_PREFIX + '/thank_you')
def thanks_for_nothing():
    return render_template('thanks_for_nothing.html')

@app.route(ROUTE_PREFIX + '/privacy')
def privacy():
    return render_template("privacy.html")


def get_db_connection():
    cl = MongoClient(SETTINGS['database']['host'], SETTINGS['database']['port'])
    db = cl[SETTINGS['database']['db']]
    if SETTINGS['database']['username'] and SETTINGS['database']['password']:
        db.authenticate(SETTINGS['database']['username'], SETTINGS['database']['password'])
    return db

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

