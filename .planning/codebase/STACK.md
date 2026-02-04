# Technology Stack

**Analysis Date:** 2026-02-03

## Languages

**Primary:**
- Python 3.10+ (3.10 - 3.14 supported) - Core orchestration engine and server
- TypeScript/JavaScript - Frontend UI applications (React and Vue-based)
- YAML - Configuration and deployment definitions
- SQL - Database schemas and migrations

**Secondary:**
- Bash/Shell - Scripts and CLI utilities
- Dockerfile - Container image building

## Runtime

**Environment:**
- Python 3.10 - 3.14 (async-first design)
- Node.js 22.12.0+ (ui-v2), Node.js 20.19.0+ (ui v1)

**Package Manager:**
- uv (Python) - Fast, reliable Python package manager with lock file (`uv.lock`)
- npm (JavaScript) - Node package manager with `package-lock.json`

## Frameworks

**Core (Python):**
- FastAPI 0.111.0+ - REST API server framework
- SQLAlchemy 2.0+ with asyncio - ORM for database operations
- Pydantic 2.10.1+ - Data validation and configuration management
- Typer 0.16.0+ - CLI application framework
- Uvicorn 0.14.0+ - ASGI server

**Frontend (ui-v2):**
- React 19.2.4 - Component-based UI framework
- TanStack Router 1.157.18+ - Type-safe router
- TanStack Query 5.90.20+ - Server state management
- TanStack Table 8.21.3+ - Data table components
- Tailwind CSS 4.0.8+ - Utility-first CSS framework
- Vite 7.3.1+ - Fast build tool and dev server

**Frontend (ui v1 - Legacy):**
- Vue 3.5.24 - Progressive JavaScript framework
- Vue Router 4.5.0 - Routing for Vue applications
- Tailwind CSS 3.4.16+ - Styling

**Testing:**
- pytest 8.3.4+ - Python testing framework
- pytest-asyncio - Async test support
- pytest-cov 6.0+ - Code coverage
- vitest 4.0.16+ - Fast unit test framework (TypeScript)
- Playwright 1.58.1+ - End-to-end testing (ui-v2)
- @testing-library - Component testing utilities (React)

**Build/Dev:**
- Alembic 1.7.5+ - Database migration tool
- ruff 0.14.14 - Fast Python linter
- mypy 1.15.0 - Static type checker
- Biome 2.3.13+ - JavaScript/TypeScript formatter and linter
- ESLint 9.39.2 - JavaScript linting (ui-v2)
- Storybook 10.1.10+ - Component development environment (ui-v2)

## Key Dependencies

**Critical:**
- asyncpg 0.23+ - PostgreSQL async driver
- aiosqlite 0.17.0+ - SQLite async driver
- httpx[http2] 0.23+ - Async HTTP client with HTTP/2 support
- websockets 15.0.1+ - WebSocket protocol implementation
- Pydantic Settings 2.2.1+ - Environment-based configuration
- amplitude-analytics 1.2.1+ - User analytics telemetry
- opentelemetry-api 1.27.0+ - Observability API

**Infrastructure:**
- docker 4.0-8.0 - Docker SDK for Python
- cryptography 36.0.1+ - Encryption and security utilities
- jinja2 3.1.6+ - Template engine
- apprise 1.1.0+ - Notification library (email, Slack, etc.)
- prometheus-client 0.20.0+ - Prometheus metrics
- orjson 3.7+ - Fast JSON serialization
- cloudpickle 2.0+ - Extended pickle support

**UI Dependencies (ui-v2):**
- @radix-ui/* - Headless UI component library
- @hookform/resolvers - Form validation
- react-markdown - Markdown rendering
- recharts 3.5.1+ - Chart components
- date-fns, date-fns-tz - Date manipulation
- zod 3.25.76+ - TypeScript schema validation
- MSW (Mock Service Worker) - API mocking

## Configuration

**Environment:**
- Environment variables with `PREFECT_` prefix
- Pydantic Settings for configuration management
- Support for `.env` files (ui-v2)
- Example: `PREFECT_API_URL`, `PREFECT_SERVER_DATABASE_CONNECTION_URL`

**Build:**
- pyproject.toml - Python project configuration with dependency groups
- setup.py style entry point: `prefect = "prefect.cli:app"`
- tsconfig.json/tsconfig.app.json - TypeScript configuration
- vite.config.ts - Vite build configuration
- biome.json - Code formatter/linter configuration
- eslint.config.js - ESLint rules
- tailwind.config.ts - Tailwind CSS configuration

**Package Management:**
- uv.lock - Deterministic Python dependency lock file
- package-lock.json - Deterministic npm lock file
- Dependency groups in pyproject.toml: dev, otel, bundles, infrastructure extras

## Platform Requirements

**Development:**
- Python 3.10+ with pip/uv
- Node.js 22.12.0 (ui-v2) or 20.19.0 (ui v1)
- PostgreSQL or SQLite for database
- Docker (optional, for containerized development)
- Git for version control

**Production:**
- Python 3.10+ runtime environment
- PostgreSQL database (or SQLite for ephemeral/lightweight deployments)
- Supported deployment targets: Docker containers, Kubernetes, cloud platforms
- OpenTelemetry support for distributed tracing
- Prometheus-compatible metrics endpoint (optional)

**Database Support:**
- Primary: PostgreSQL with async support (asyncpg)
- Alternative: SQLite with async support (aiosqlite)
- Migrations managed by Alembic
- Connection pooling configured via SQLAlchemy

## Optional Extras

**Infrastructure Platforms:**
- AWS (prefect-aws)
- Azure (prefect-azure)
- GCP (prefect-gcp)
- Docker (prefect-docker)
- Kubernetes (prefect-kubernetes)
- Shell execution (prefect-shell)

**Distributed Execution:**
- Dask (prefect-dask)
- Ray (prefect-ray)

**Version Control Integration:**
- GitHub (prefect-github)
- GitLab (prefect-gitlab)
- Bitbucket (prefect-bitbucket)

**Database/Data Tools:**
- Databricks (prefect-databricks)
- dbt (prefect-dbt)
- Snowflake (prefect-snowflake)
- SQLAlchemy (prefect-sqlalchemy)
- Redis (prefect-redis)

**Monitoring:**
- Email notifications (prefect-email)
- Slack integration (prefect-slack)

**Bundle Support:**
- uv 0.6.0+ (required for bundle features)

**OpenTelemetry:**
- opentelemetry-distro 0.48b0+
- opentelemetry-exporter-otlp 1.27.0+
- opentelemetry-instrumentation with logging support

---

*Stack analysis: 2026-02-03*
