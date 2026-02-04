# External Integrations

**Analysis Date:** 2026-02-03

## APIs & External Services

**Analytics:**
- Amplitude Analytics - User telemetry and usage tracking
  - SDK/Client: `amplitude-analytics>=1.2.1,<2.0.0`
  - Implementation: `src/prefect/_internal/analytics/client.py`
  - Auth: `AMPLITUDE_API_KEY` (build-time configuration)
  - Purpose: Anonymous SDK usage metrics, onboarding tracking

**Observability:**
- OpenTelemetry - Distributed tracing and instrumentation
  - SDK: `opentelemetry-api>=1.27.0,<2.0.0`
  - Exporters: OTLP exporter available via optional `otel` extra
  - Purpose: Tracing, metrics, and instrumentation across SDK and server
  - Optional instrumentation packages: logging, HTTP, database

**HTTP & Webhooks:**
- httpx - Async HTTP client library
  - Version: `httpx[http2]>=0.23,!=0.23.2`
  - Purpose: API calls, webhook interactions, HTTP/2 support
  - Used for: Client-to-server communication, external service calls

**Notifications:**
- Apprise - Multi-service notification library
  - Version: `apprise>=1.1.0,<2.0.0`
  - Purpose: Unified notification interface for email, Slack, webhooks
  - Protocols supported: Email (SMTP), Slack, webhook endpoints, many others

## Data Storage

**Databases:**
- PostgreSQL (Primary)
  - Connection: Async via `asyncpg>=0.23,<1.0.0`
  - ORM: SQLAlchemy 2.0+ with asyncio
  - Migrations: Alembic
  - Environment variable: `PREFECT_SERVER_DATABASE_CONNECTION_URL`
  - Configuration: `src/prefect/settings/models/server/database.py`
  - Features: mTLS support, connection pooling, search_path configuration

- SQLite (Development/Lightweight)
  - Connection: Async via `aiosqlite>=0.17.0,<1.0.0`
  - ORM: SQLAlchemy 2.0+ with asyncio
  - Purpose: Development, ephemeral deployments, testing
  - Built from source (SQLite 3.50.4) to address CVE-2025-6965

**File Storage:**
- Local filesystem only for core functionality
- fsspec 2022.5.0+ available for extensible file system access
- Artifacts stored in configurable locations

**Caching:**
- In-memory caching via cachetools 5.3+
- Optional Redis integration via prefect-redis optional dependency
- No built-in external caching service required

## Authentication & Identity

**Auth Provider:**
- Custom JWT-based authentication
  - API key stored in environment: `PREFECT_API_KEY`
  - API URL endpoint: `PREFECT_API_URL` (default: https://api.prefect.cloud/api)
  - CSRF token support (managed by client)
  - Custom headers support via `PREFECT_CLIENT_CUSTOM_HEADERS`

**Prefect Cloud:**
- Optional integration with Prefect Cloud SaaS
- Connection: `src/prefect/settings/models/cloud.py`
- Configuration:
  - `PREFECT_CLOUD_API_URL` - Cloud API endpoint
  - `PREFECT_CLOUD_UI_URL` - Cloud UI URL (inferred if not set)
  - `PREFECT_CLOUD_MAX_LOG_SIZE` - Log size limit (default 25,000 chars)
  - Orchestration telemetry flag

## Monitoring & Observability

**Error Tracking:**
- None built-in; OpenTelemetry can integrate with error tracking services
- Application logs sent to Prefect API via `LoggingToAPISettings`

**Logs:**
- API-based logging: Logs can be sent to Prefect API
  - Environment: `PREFECT_LOGGING_TO_API_ENABLED` (default: true)
  - Batch interval: `PREFECT_LOGGING_TO_API_BATCH_INTERVAL` (default: 2.0s)
  - Batch size: `PREFECT_LOGGING_TO_API_BATCH_SIZE` (default: 4,000,000)
  - Max log size: `PREFECT_LOGGING_TO_API_MAX_LOG_SIZE` (default: 1,000,000 chars)
- File-based logging via configurable logger
- Python logging integration with custom formatters

**Metrics:**
- Prometheus metrics exposure
  - Client metrics: `PREFECT_CLIENT_METRICS_ENABLED` (default: false, port 4201)
  - Server metrics: `PREFECT_SERVER_METRICS_ENABLED` (default: false)
  - prometheus-client 0.20.0+ for exposition

## CI/CD & Deployment

**Hosting:**
- Container-based (Docker) - Dockerfile provided with Python, Node build stages
- Kubernetes-ready (optional prefect-kubernetes integration)
- Cloud deployments (AWS, Azure, GCP via optional integrations)
- Self-hosted on any infrastructure with Python 3.10+ and PostgreSQL

**CI Pipeline:**
- GitHub Actions (workflows in `.github/`)
- Docker image builds with multi-stage compilation
- SQLite built from source for security (CVE-2025-6965)
- UI builds included in container image (v1 and v2)

## Environment Configuration

**Required env vars:**
- `PREFECT_API_URL` - API endpoint for client connections
- `PREFECT_API_KEY` - Authentication token
- `PREFECT_SERVER_DATABASE_CONNECTION_URL` - Database connection string (if using PostgreSQL)
- `PREFECT_CLOUD_API_URL` - Cloud API endpoint (if using Prefect Cloud)

**Optional env vars:**
- `PREFECT_DEBUG` - Enable debug mode
- `PREFECT_LOGGING_LEVEL` - Logging verbosity
- `PREFECT_SERVER_METRICS_ENABLED` - Prometheus metrics
- `PREFECT_SERVER_LOGGING_LEVEL` - Server logging level
- `PREFECT_LOGGING_TO_API_ENABLED` - Send logs to API
- `PREFECT_CLIENT_METRICS_ENABLED` - Client Prometheus metrics
- `VITE_AMPLITUDE_API_KEY` - Frontend analytics (ui-v2 build-time)
- `VITE_API_URL` - Frontend API URL (ui-v2 development)

**Secrets location:**
- Environment variables (recommended)
- .env files (development only, not committed)
- Container secrets management systems
- Environment variable substitution in URLs

## Webhooks & Callbacks

**Incoming:**
- Webhook endpoints available via FastAPI (generic HTTP endpoints)
- HTTP POST receivers configured via Apprise for incoming notifications
- Event streaming available via WebSocket connections

**Outgoing:**
- Webhook dispatching via httpx async client
- Apprise-based notification dispatch to external services
- Event publishing to external systems via HTTP
- Support for custom webhook URLs in deployment configuration

## Integration Extensions (Optional)

**Infrastructure as Code:**
- AWS: prefect-aws 0.5.8+ (EC2, ECS, Lambda, S3)
- Azure: prefect-azure 0.4.0+ (Container Instances, Blob Storage)
- GCP: prefect-gcp 0.6.0+ (Cloud Run, Cloud Storage)

**Data Platforms:**
- Databricks: prefect-databricks 0.3.0+
- Snowflake: prefect-snowflake 0.28.0+
- dbt: prefect-dbt 0.6.0+
- SQLAlchemy: prefect-sqlalchemy 0.5.0+ (generic SQL databases)

**Distributed Computing:**
- Dask: prefect-dask 0.3.0+
- Ray: prefect-ray 0.4.0+

**Version Control:**
- GitHub: prefect-github 0.3.0+
- GitLab: prefect-gitlab 0.3.0+
- Bitbucket: prefect-bitbucket 0.3.0+

**Notifications:**
- Email: prefect-email 0.4.0+ (via SMTP)
- Slack: prefect-slack 0.3.0+ (via Slack API)

## API Standards

**REST API:**
- OpenAPI 3.x specification
- Served by FastAPI
- CSRF token validation (if enabled via `PREFECT_CLIENT_CSRF_SUPPORT_ENABLED`)
- Automatic API documentation at `/docs`

**Client Retry Logic:**
- Max retries: Configurable (default 5) via `PREFECT_CLIENT_MAX_RETRIES`
- Jitter: Configurable factor (default 0.2) via `PREFECT_CLIENT_RETRY_JITTER_FACTOR`
- Status codes: Always retries 429, 502, 503; configurable extras via `PREFECT_CLIENT_RETRY_EXTRA_CODES`

---

*Integration audit: 2026-02-03*
