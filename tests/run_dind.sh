#!/bin/bash

set -e

# port
port=${1:-80}

docker rm -f eofe-manager || true
docker rm -f eofe-worker || true
# サーバーコンテナイメージビルド
tar czvf tests/backend.tar.gz backend
cp run.sh tests
docker build tests -t eofe-test:latest
rm -f tests/backend.tar.gz tests/run.sh

docker network create eofe-network || true
docker volume create eofe-certs-ca
docker volume create eofe-certs-client

docker run --privileged --name eofe-manager -itd \
	--network eofe-network --network-alias docker \
	-e DOCKER_TLS_CERTDIR=/certs \
	-v eofe-certs-ca:/certs/ca \
	-v eofe-certs-client:/certs/client \
    -p ${port}:8000 \
	eofe-test:latest

sleep 5

docker exec eofe-manager docker swarm init
swarm_token=$(docker exec eofe-manager docker swarm join-token -q worker)

docker run --privileged --name eofe-worker -d \
	--network eofe-network --network-alias docker \
	-e DOCKER_TLS_CERTDIR=/certs \
	-v eofe-certs-ca:/certs/ca \
	-v eofe-certs-client:/certs/client \
	docker:dind

sleep 5

docker exec eofe-worker docker swarm join --token $swarm_token eofe-manager:2377
