#!/bin/bash

set -e

# port
port=${1:? "Usage: $0 <port>"}

docker rm -f taskhub-manager || true
docker rm -f taskhub-worker || true
# サーバーコンテナイメージビルド
tar czvf tests/backend.tar.gz backend
cp run.sh tests
docker build tests -t taskhub-test:latest
rm -f tests/backend.tar.gz tests/run.sh

docker network create taskhub-network || true
docker volume create taskhub-certs-ca
docker volume create taskhub-certs-client

docker run --privileged --name taskhub-manager -itd \
	--network taskhub-network --network-alias docker \
	-e DOCKER_TLS_CERTDIR=/certs \
	-v taskhub-certs-ca:/certs/ca \
	-v taskhub-certs-client:/certs/client \
    -p ${port}:8000 \
	taskhub-test:latest

sleep 5

docker exec taskhub-manager docker swarm init
swarm_token=$(docker exec taskhub-manager docker swarm join-token -q worker)

docker run --privileged --name taskhub-worker -d \
	--network taskhub-network --network-alias docker \
	-e DOCKER_TLS_CERTDIR=/certs \
	-v taskhub-certs-ca:/certs/ca \
	-v taskhub-certs-client:/certs/client \
	docker:dind

sleep 5

docker exec taskhub-worker docker swarm join --token $swarm_token taskhub-manager:2377
