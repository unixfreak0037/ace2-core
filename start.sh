#!/usr/bin/env bash
export WORKER_CLASS=${WORKER_CLASS:-"uvicorn.workers.UvicornWorker"}

if [ -z "$ACE_ADMIN_PASSWORD" ]
then
    echo "ERROR: missing ACE_ADMIN_PASSWORD environment variable"
    exit 1
fi

cd /opt/ace && exec gunicorn -k "$WORKER_CLASS" -c "/opt/ace/gunicorn_conf.py"  ace.system.distributed:app
