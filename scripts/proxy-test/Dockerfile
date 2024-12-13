FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install uv
RUN uv pip install --no-cache-dir --system -r requirements.txt

COPY server.py .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
