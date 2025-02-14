#!/bin/bash

set -e -o pipefail

repo_url=${1:-https://github.com/obeh29380/taskhub-problems.git}

git clone $repo_url || true
dir=$(cd $(dirname $0); pwd)
repo_dir=$dir/$(basename "$repo_url" .git)
echo "Checking repository..."
res_status=$(curl -sL -o /dev/null -w '%{http_code}' $repo_url)
if [ $res_status -ne 200 ]; then
  echo "Error: Repositry not found [$res_status]"
  exit 1
fi

# dockerが起動するまで待つ
until docker info > /dev/null 2>&1; do
  sleep 1
done

docker rm -fv taskhub || true
docker service rm taskhub || true
docker build -t taskhub:latest backend

echo "problems dir: $repo_dir"
# 現状gitから取れない場合エラーになるので、そもそもディレクトリなしでここに到達しない
# ls -la $repo_dir || mkdir -p $repo_dir

docker service create \
  --name taskhub \
  --replicas 1 \
  --publish 8000:8000 \
  --mount type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock \
  --mount type=bind,src=$repo_dir,dst=/app/taskhub-problems \
  --mount type=bind,src=$dir/backend/certs,dst=/app/certs \
  --env REPO_URL=$repo_url \
  --env ADMIN_PASSWORD=admin \
  --env DOCKER_SERVICE_CPU_LIMIT=0.5 \
  --env DOCKER_SERVICE_MEM_LIMIT=1 \
  --restart-condition any \
  taskhub:latest