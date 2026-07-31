#!/bin/bash

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
	return 1
fi

modoboa-admin.py deploy instance \
	--dburl default:${DB_CONN} \
	--timezone ${TIMEZONE} \
	--collectstatic --devel

mkdir dkim
if [[ -d ./backup ]]; then
	echo "Modoboa backup restoring..."
	source ./backup/run.sh
else
	echo "Modoboa initializing..."
	python3 manage.py migrate
	python3 manage.py load_initial_data
fi
python3 manage.py set_default_site ${DOMAIN} --frontend

cp -r /usr/local/lib/python3.13/dist-packages/modoboa/frontend_dist/* www/

cat <<EOF >gunicorn.conf.py
accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = "info"
bind = "0.0.0.0:8000"
EOF

echo "REDIS_HOST=${REDIS_CONN%:*}" >>.env
echo "REDIS_PORT=${REDIS_CONN#*:}" >>.env

echo "Modoboa starting..."
gunicorn instance:wsgi
