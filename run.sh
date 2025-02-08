#!/bin/bash

# dockerが起動するまで待つ
until docker info > /dev/null 2>&1; do
  sleep 1
done

sleep 5

docker swarm init

docker rm -fv ccpp
docker build -t ccpp:latest backend
docker run -d -p 8000:8000 -v /var/run/docker.sock:/var/run/docker.sock --name ccpp ccpp:latest
