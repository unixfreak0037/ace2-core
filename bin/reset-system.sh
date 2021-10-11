#!/usr/bin/env bash

bin/stop-system.sh
docker volume ls | awk '{print $2}' | grep ace2-core_ | while read volume
do
    docker volume rm $volume
done
bin/initialize-system.sh
