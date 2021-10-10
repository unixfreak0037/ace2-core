#!/usr/bin/env bash

docker-compose run --rm ace acecli initialize | sed -ne '/^# START EXPORT/,/^# STOP EXPORT/ p' | tr -d '\r' > .ace-env
chmod 600 .ace-env
source .ace-env
docker-compose down
