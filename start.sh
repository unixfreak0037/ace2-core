#!/usr/bin/env bash
if [ -z "$ACE_API_KEY" ]
then
    echo "ERROR: missing ACE_API_KEY environment variable"
    exit 1
fi

export WORKER_CLASS=${WORKER_CLASS:-"uvicorn.workers.UvicornWorker"}
source .venv/bin/activate
exec gunicorn -k "$WORKER_CLASS" -c "/opt/ace/gunicorn_conf.py"  ace.system.distributed:app
