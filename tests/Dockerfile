FROM docker:dind

RUN apk add --no-cache \
    bash \
    py3-pip \
    python3 \
    curl

RUN mkdir /app
WORKDIR /app

COPY backend.tar.gz .
COPY run.sh .
COPY run_swarm.sh .

RUN tar -xvzf backend.tar.gz && \
    python3 -m pip install -r ./backend/requirements.txt --break-system-packages && \
    rm -f backend.tar.gz

# CMD [ "bash", "run.sh" ]
