# Smapp / ANES facebook survey addon
This web app allows users to authorize a facebook app for data collection, to be used as a part of a survey.


**Runs on python 2.7**

### Moving parts
* a web app which enables users to authorize a facebook app and grant it permission to view their data
* a mongodb database in which the web app stores the user tokens it receives
* a script that checks the database for new user tokens, downloads their data, and uploads it to a server

### Development
Start by copying the file `settings.yml.example` to `settings.yml`, and editing it to reflect your settings (facebook app id, database location, etc).

For local testing, `vagrant up` sets up a fully functional self-contained app server serving the app.

### Deployment
To mimick our deployment, clone this repo onto a server, provision it using #TODO, and voila.


-----------
Code and documentation &copy; 2014 New York University. Released under [the GPLv2 license](LICENSE).

@jonathanronen

