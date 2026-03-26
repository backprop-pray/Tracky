FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/patatnik

COPY requirements/runpod-batch2-py310.txt /tmp/runpod-batch2-py310.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /tmp/runpod-batch2-py310.txt

COPY . /workspace/patatnik

CMD ["/bin/bash"]
