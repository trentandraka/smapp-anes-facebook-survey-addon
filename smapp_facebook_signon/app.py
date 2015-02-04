import os
import yaml
import facebook
from flask import Flask
from pymongo import MongoClient
from flask import render_template, url_for, request, redirect


app = Flask(__name__)
this_path = os.path.dirname(os.path.realpath(__file__))
SETTINGS = yaml.load(open(os.path.join(this_path, 'settings.yml')))



FACEBOOK_LINK = "https://www.facebook.com/dialog/oauth?response_type=token&client_id={app_id}&redirect_uri={callback}"
@app.route('/')
def welcome():
    facebook_link = FACEBOOK_LINK.format(
        app_id=SETTINGS['facebook']['app_id'],
        callback="http://localhost:5000" + url_for('callback_from_fb'))
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
    user = g.get_object("me")
    db = get_db_connection()
    db.users.save({
        "user": user,
        "token": res
        })
    return redirect(url_for('thanks', userid=user['id']))

@app.route('/thanks/<userid>')
def thanks(userid):
    name = get_db_connection().users.find_one({'user.id': userid})['user']['name']
    return render_template("thanks.html", name=name)


def get_db_connection():
    cl = MongoClient(SETTINGS['database']['host'], SETTINGS['database']['port'])
    db = cl[SETTINGS['database']['db']]
    db.authenticate(SETTINGS['database']['username'], SETTINGS['database']['password'])
    return db

if __name__ == '__main__':
    app.run(debug=True)

