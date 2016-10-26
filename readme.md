# Smapp / ANES facebook survey addon
This web app allows users to authorize a facebook app for data collection, to be used as a part of a survey.


**Runs on python 2.7**

### Moving parts
* a web app which enables users to authorize a facebook app and grant it permission to view their data
* a mongodb database in which the web app stores the user tokens it receives
* a script that checks the database for new user tokens, downloads their data, and uploads it to a server

##### Approved IDs
There is an optional validation of user entered IDs in the welcome page. In order to make use of it, make a text file where each approved ID is entered on a single line, and give the path to that file in `settings.yaml`, under the name `approved-ids-filename`. See `settings.yaml.example`.

### Development
Start by copying the file `settings.yml.example` to `settings.yml`, and editing it to reflect your settings (facebook app id, database location, etc).

For local testing, `vagrant up` sets up a fully functional self-contained app server serving the app.

### Deployment
To mimick our deployment, clone this repo onto a server, provision it using #TODO.

#### gunicorn + nginx
To serve using gunicorn via nginx, one might run the gunicorn app locally at http://localhost:8000 and configure a reverse-proxy to application at :80. We serve the app at `http://example.com/facebook` (with `http://example.com/` displaying a different page). Here's an nginx config that does that:

```
server {
        listen 80 default_server;
        listen [::]:80 default_server ipv6only=on;

        root /usr/share/nginx/html;
        index index.html index.htm;

        # Make site accessible from http://localhost/
        server_name localhost;

        location /facebook {
            proxy_set_header X-Forward-For $proxy_add_x_forwarded_for;
            proxy_set_header Host $http_host;
            proxy_redirect off;
            if (!-f $request_filename) {
                proxy_pass http://127.0.0.1:8000;
                break;
            }
        }
        location /static {
            proxy_set_header X-Forward-For $proxy_add_x_forwarded_for;
            proxy_set_header Host $http_host;
            proxy_redirect off;
            if (!-f $request_filename) {
                proxy_pass http://127.0.0.1:8000;
                break;
            }
        }
    }
```

This serves both `/facebook` and `/static` to the gunicorn app. There's probably a cleaner way to do this. With this, `app-prefix: /facebook` should be set in `settings.yml`. With `app-prefix: /` one location in the nginx config would suffice.

-----------
Code and documentation &copy; 2014 New York University. Released under [the GPLv2 license](LICENSE).

@jonathanronen

