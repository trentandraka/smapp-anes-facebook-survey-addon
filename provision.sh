# Just update
sudo apt-get update
sudo apt-get upgrade

# Some basic security
sudo apt-get -y install fail2ban
# sudo apt-get install unattended-up..

# Some server stuff we need
sudo apt-get -y install git-core nginx

# Mongodb
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv EA312927
echo "deb http://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/3.2 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.2.list
sudo apt-get update
sudo apt-get -y install mongodb-org
sudo systemctl start mongod.service
sudo systemctl enable mongod.service

export LC_ALL=C

## The following to set up the app
git clone https://github.com/jonathanronen/smapp-anes-facebook-survey-addon.git
cd smapp-anes-facebook-survey-addon
sudo apt-get -y install python-pip
sudo pip install -U pip
sudo apt-get install -y python-virtualenv
sudo pip install virtualenv
sudo pip install virtualenvwrapper

echo "export WORKON_HOME=~/.virtualenvs" >> ~/.bashrc
echo ". /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
source ~/.bashrc 

mkdir ~/.virtualenvs
mkvirtualenv smapp-anes

pip install -r requirements.txt
pip install gunicorn

sudo mv /etc/nginx/sites-available/default /etc/nginx/sites-available/config.backup
sudo cp nginx.default.config /etc/nginx/sites-available/default
sudo systemctl restart nginx.service