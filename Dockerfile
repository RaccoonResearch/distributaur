FROM --platform=linux/x86_64 ubuntu:24.04

RUN apt-get update && \
    apt-get install -y \
    wget \
    xz-utils \
    bzip2 \
    python3-pip \
    python3 \
    && apt-get install -y software-properties-common

COPY requirements.txt .

RUN pip install -r requirements.txt --break-system-packages

COPY distributaur/ ./distributaur/

CMD ["celery", "-A", "distributaur.example_worker", "worker", "--loglevel=info", "--concurrency=1"]