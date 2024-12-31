# investigating server performance

requirements:

- docker
- opentelemetry libraries

```bash
uv pip install opentelemetry-api \
                opentelemetry-sdk \
                opentelemetry-exporter-otlp \
                opentelemetry-instrumentation-sqlalchemy \
                opentelemetry-instrumentation-fastapi
```

#### note

allow the following scripts to run via `chmod +x` (or similar)

```bash
./load_testing/local-telemetry/start
./load_testing/run-server.sh
./load_testing/populate-server.sh
```

### start the local telemetry stack

```bash
./load_testing/local-telemetry/start
```

### run the server with tracing

You can run the server with either SQLite (default) or PostgreSQL using the `run-server.sh` script:

```bash
# Run with SQLite (default)
./load_testing/run-server.sh

# Run with PostgreSQL 15
./load_testing/run-server.sh postgres:15
```

The script will:
- For SQLite: Use the default SQLite configuration
- For PostgreSQL: 
  - Start a Docker container with the specified version
  - Configure the database connection
  - Handle container lifecycle (reuse if possible, recreate if version changes)

If you need to run the server manually, here are the environment variables used:

```bash
prefect config set PREFECT_API_URL=http://localhost:4200/api

unset $(env | grep OTEL_ | cut -d= -f1)
export OTEL_SERVICE_NAME=prefect-server
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_LOG_LEVEL=debug
export PYTHONPATH=src
```

### populate the server

create a work pool and some deployments
```bash
./load_testing/populate-server.sh
```

### start a worker

```bash
prefect worker start --pool local
```
