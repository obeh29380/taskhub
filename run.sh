docker rm -fv ccpp
docker build -t ccpp:latest backend && \
docker run --rm -d -p 8000:8000 -v /var/run/docker.sock:/var/run/docker.sock --name ccpp ccpp:latest
