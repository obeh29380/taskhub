#!/bin/bash

set -e -o pipefail

if [ -z "$1" ]; then
  echo "Error: url must be specified <arg1>"
  exit 1
fi
repo_url=$1
res_status=$(curl -sL -o /dev/null -w '%{http_code}' $repo_url)
if [ $res_status -ne 200 ]; then
  echo "Error: Repositry not found [$res_status]"
  exit 1
fi

# dockerが起動するまで待つ
until docker info > /dev/null 2>&1; do
  sleep 1
done

sleep 5

docker rm -fv ccpp
docker build -t ccpp:latest backend
docker run -d -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v  /app/taskhub-problems/ \
  -e REPO_URL=$repo_url \
  -e ADMIN_PASSWORD=admin \
  --name ccpp ccpp:latest
