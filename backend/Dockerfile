FROM python:3.11-slim

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY server.py /app/server.py

CMD ["python3", "/app/server.py"]
