# Tests
Tests are run against SQLite and Postgres.

## Database Fixtures
Database fixtures (found at `./fixtures/database.py`) manipulate database state before tests run. They are most commonly used to populate the database with useful information so that tests don't need to create every object they need manually. 

When writing a database fixture, consider these best practices:
- use the global `session` fixture
- use any internal means of creating or manipulating a database object (for example, the internal `models` functions)
- commit the session (this makes any changes visible to other actors)
- return any relevant database objects

Consider this example:

```python
@pytest.fixture
async def flow(session):
    model = await models.flows.create_flow(
        session=session, 
        flow=schemas.actions.FlowCreate(name="my-flow"),
    )
    await session.commit()
    return model
```
