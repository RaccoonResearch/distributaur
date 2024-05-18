FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y \
    wget \
    xz-utils \
    bzip2 \
    python3-pip \
    python3 \
    python3 -m pip install --upgrade pip

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY distributaur/ ./distributaur/

CMD ["celery", "-A", "distributaur.task_runner", "worker", "--loglevel=info", "--concurrency=1"]