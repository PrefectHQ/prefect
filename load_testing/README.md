
# investigating server performance

requirements:

- docker
- opentelemetry libraries

```bash
» uv pip install opentelemetry-api \
                opentelemetry-sdk \
                opentelemetry-exporter-otlp \
                opentelemetry-instrumentation-sqlalchemy \
                opentelemetry-instrumentation-fastapi
```


### start the local telemetry stack

```bash
./load_testing/local-telemetry/start
```

### run the server with tracing


```bash

» prefect config set PREFECT_API_URL=http://localhost:4200/api

» unset $(env | grep OTEL_ | cut -d= -f1)
export OTEL_SERVICE_NAME=prefect-server
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_LOG_LEVEL=debug
export PYTHONPATH=/Users/nate/github.com/prefecthq/prefect/src


» opentelemetry-instrument \
  uvicorn \
  --app-dir /Users/nate/github.com/prefecthq/prefect/src \
  --factory prefect.server.api.server:create_app \
  --host 127.0.0.1 \
  --port 4200 \
  --timeout-keep-alive 5
```

### populate the server

if you haven't before, allow the script to run

```bash
chmod +x load_testing/populate-server.sh
```

create a work pool and some deployments
```bash
./load_testing/populate-server.sh
```


### start a worker

```bash
prefect worker start --pool local
```
