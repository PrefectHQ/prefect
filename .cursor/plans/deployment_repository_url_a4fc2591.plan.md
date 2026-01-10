---
name: Deployment Repository URL
overview: Deployment 모델에 code_repository_url 필드를 추가하고, UI에서 해당 링크를 표시하여 사용자가 코드 저장소로 쉽게 이동할 수 있도록 합니다.
todos:
  - id: backend-orm
    content: Add code_repository_url column to Deployment ORM model
    status: completed
  - id: backend-migration
    content: Create Alembic migrations for PostgreSQL and SQLite
    status: completed
    dependencies:
      - backend-orm
  - id: backend-schemas
    content: Add code_repository_url field to all Pydantic schemas (core, actions, responses, client)
    status: completed
    dependencies:
      - backend-orm
  - id: backend-tests
    content: Add backend tests for new field
    status: completed
    dependencies:
      - backend-schemas
  - id: frontend-sync
    content: Run npm run service-sync to regenerate TypeScript types
    status: pending
    dependencies:
      - backend-schemas
  - id: frontend-ui
    content: Add Repository URL display to deployment-metadata.tsx
    status: completed
    dependencies:
      - frontend-sync
  - id: frontend-tests
    content: Update Storybook stories and add component tests
    status: completed
    dependencies:
      - frontend-ui
---

# Deployment Repository URL Feature

This PR adds the ability to store and display a code repository URL for deployments, addressing [issue #19834](https://github.com/PrefectHQ/prefect/issues/19834).

## Architecture Overview

```mermaid
flowchart TB
    subgraph Backend
        ORM[orm_models.py<br/>DB Column]
        Core[schemas/core.py]
        Actions[schemas/actions.py]
        Responses[schemas/responses.py]
        Client[client/schemas/objects.py]
        Migration[Alembic Migration]
    end
    
    subgraph Frontend
        PrefectTS[prefect.ts<br/>Auto-generated]
        Metadata[deployment-metadata.tsx]
    end
    
    ORM --> Migration
    ORM --> Core
    Core --> Actions
    Core --> Responses
    Core --> Client
    Responses --> PrefectTS
    PrefectTS --> Metadata
```

## Implementation

### 1. Backend - Database Schema

Add `code_repository_url` column to Deployment table:

**[src/prefect/server/database/orm_models.py](src/prefect/server/database/orm_models.py)**

```python
class Deployment(Base):
    # ... existing fields ...
    code_repository_url: Mapped[Optional[str]] = mapped_column(sa.Text())
```

### 2. Backend - Create Alembic Migrations

Generate migration files for both PostgreSQL and SQLite:

```bash
cd src/prefect/server/database/_migrations/versions
# Create migration files manually following existing patterns
```

- PostgreSQL: `versions/postgresql/YYYY_MM_DD_HHMMSS_add_code_repository_url_to_deployment.py`
- SQLite: `versions/sqlite/YYYY_MM_DD_HHMMSS_add_code_repository_url_to_deployment.py`

### 3. Backend - Update Pydantic Schemas

Add field to all relevant schemas:

**[src/prefect/server/schemas/core.py](src/prefect/server/schemas/core.py)** - `Deployment` class

**[src/prefect/server/schemas/actions.py](src/prefect/server/schemas/actions.py)** - `DeploymentCreate`, `DeploymentUpdate` classes

**[src/prefect/server/schemas/responses.py](src/prefect/server/schemas/responses.py)** - `DeploymentResponse` class

**[src/prefect/client/schemas/objects.py](src/prefect/client/schemas/objects.py)** - Client `Deployment` class

```python
code_repository_url: Optional[str] = Field(
    default=None,
    description="URL to the code repository for this deployment.",
)
```

### 4. Frontend - Sync API Types

```bash
cd ui-v2
npm run service-sync  # Regenerates prefect.ts from OpenAPI schema
```

### 5. Frontend - Display Repository Link in UI

**[ui-v2/src/components/deployments/deployment-metadata.tsx](ui-v2/src/components/deployments/deployment-metadata.tsx)**

Add Repository URL field to `BOTTOM_FIELDS` array, rendering as a clickable external link when present.

### 6. Testing

- **Backend**: Add tests for the new field in deployment create/update/read operations
- **Frontend**: Update Storybook story with mock data containing `code_repository_url`

## Scope Limitations (First PR)

- Input is only via API/SDK (no UI form for editing repository URL yet)
- No automatic git ref/commit linking (future enhancement)
- No deep linking to specific files (future enhancement)

## Verification

1. Run `prefect server start`
2. Create a deployment with `code_repository_url` via API
3. View Deployment details page and confirm Repository link appears