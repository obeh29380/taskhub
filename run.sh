#!/bin/bash

set -e -o pipefail

repo_url=${1:-}

if [ -n "$repo_url" ]; then
  echo "Checking repository..."
  res_status=$(curl -sL -o /dev/null -w '%{http_code}' $repo_url)
  if [ $res_status -ne 200 ]; then
    echo "Error: Repositry not found [$res_status]"
    exit 1
  fi
fi

# dockerが起動するまで待つ
until docker info > /dev/null 2>&1; do
  sleep 1
done

sleep 5

docker rm -fv ccpp
docker build -t ccpp:latest backend

repo_dir=./taskhub-problems


if [ -n "$repo_url" ]; then
  docker run -d -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $repo_dir:/app/taskhub-problems/ \
  -e REPO_URL=$repo_url \
  -e REPO_DIR=$repo_dir \
  -e ADMIN_PASSWORD=admin \
  --name ccpp ccpp:latest
else
  docker run -d -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $repo_dir:/app/taskhub-problems/ \
  -e REPO_DIR=$repo_dir \
  -e ADMIN_PASSWORD=admin \
  --name ccpp ccpp:latest
fi