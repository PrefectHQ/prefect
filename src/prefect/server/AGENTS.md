# Prefect Server

This directory contains the Prefect server implementation - the orchestration backend that manages flow runs, scheduling, and state tracking.

## Core Components  

- `api/` - FastAPI REST API endpoints for client communication
- `database/` - Database models, migrations, and connection management
- `orchestration/` - Flow and task run orchestration logic
- `schemas/` - Pydantic models for API request/response validation
- `services/` - Background services (scheduler, flow run engine, etc.)
- `models/` - SQLAlchemy database models
- `events/` - Event system for real-time updates and webhooks

## Architecture

The server uses:
- **FastAPI** for the REST API layer
- **SQLAlchemy** for database abstraction (supports SQLite, PostgreSQL)
- **Alembic** for database migrations  
- **Async/await** patterns throughout for high concurrency
- **Pydantic** for data validation and serialization

## Key Services

- **Scheduler**: Manages flow run scheduling based on deployments
- **Flow Run Engine**: Orchestrates individual flow executions
- **Task Queue**: Handles async task processing
- **Event Publisher**: Publishes workflow events for monitoring

## Development Notes

- Server can run standalone or embedded in client processes
- Database operations use async patterns with connection pooling
- API follows REST conventions with OpenAPI documentation
- All state changes go through the orchestration layer for consistency 