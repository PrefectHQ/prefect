FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


ENV UV_SYSTEM_PYTHON=1
ENV PATH="/root/.local/bin:$PATH"

COPY requirements.txt .

RUN uv pip install -r requirements.txt

