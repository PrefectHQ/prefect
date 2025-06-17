# Prefect Server

Orchestration backend managing flow runs, scheduling, and state tracking.

## Key Components

- **API**: FastAPI REST endpoints for client communication
- **Database**: SQLAlchemy models and Alembic migrations
- **Orchestration**: Flow/task run state management and policies
- **Services**: Background scheduler, event publisher, task queue

## Main Directories

- `api/` - REST API endpoints
- `database/` - Database connections and migrations
- `models/` - SQLAlchemy ORM models
- `schemas/` - Pydantic request/response models
- `orchestration/` - State transition rules
- `services/` - Background services

## Server-Specific Notes

- Supports SQLite (development) and PostgreSQL (production)
- Async throughout for high concurrency
- Can run standalone or embedded in client processes
- All state changes go through orchestration layer