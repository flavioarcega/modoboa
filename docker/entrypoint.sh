#!/bin/bash

set -e # stop on error
set -x # show execution (debug)

if [[ ! -v DOMAIN ]]; then
	UNDEFINED="${UNDEFINED} - DOMAIN\n"
fi
if [[ ! -v TIMEZONE ]]; then
	UNDEFINED="${UNDEFINED} - TIMEZONE\n"
fi
if [[ ! -v REDIS_CONN ]]; then
	UNDEFINED="${UNDEFINED} - REDIS_CONN\n"
fi
if [[ ! -v DB_CONN ]]; then
	UNDEFINED="${UNDEFINED} - DB_CONN\n"
fi

if [[ -v UNDEFINED ]]; then
	echo "Undefined environment variables:\n${UNDEFINED}"
	exit 1
fi

modoboa-admin.py deploy instance --devel --domain ${DOMAIN} --timezone ${TIMEZONE} --dburl default:${DB_CONN}

echo "REDIS_HOST=${REDIS_CONN%:*}" >>.env
echo "REDIS_PORT=${REDIS_CONN#*:}" >>.env

if [[ -d /home/modoboa/backup ]]; then
	echo "Modoboa backup restoring..."
	source /home/modoboa/backup/run.sh
else
	echo "Modoboa initializing..."
	python3 manage.py migrate
	python3 manage.py load_initial_data
fi
python3 manage.py set_default_site ${DOMAIN} --frontend

cat <<EOF >gunicorn.conf.py
accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = "info"
bind = "0.0.0.0:8000"
EOF

echo "Modoboa starting..."
gunicorn instance.wsgi
