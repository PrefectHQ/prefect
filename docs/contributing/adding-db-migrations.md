# Adding Database Migrations
To make changes to a table, first update the SQLAlchemy model in `src/prefect/server/database/orm_models.py`. For example
if you wanted to add a new column to the `flow_run` table, you would add a new column to the `FlowRun` model:

```python
# src/prefect/server/database/orm_models.py

@declarative_mixin
class ORMFlowRun(ORMRun):
    """SQLAlchemy model of a flow run."""
    ...
    new_column = Column(String, nullable=True) # <-- add this line
```

Next, you will need to generate a new migration file. You will need to generate a new migration file for each database type. 
Migrations will be generated for whatever database type `PREFECT_API_DATABASE_CONNECTION_URL` is set to.

To generate a new migration file, run the following command:

<div class="terminal">
```bash
prefect server database revision --autogenerate -m "add_flow_run__new_column"
```
</div>

The `--autogenerate` flag will automatically generate a migration file based on the changes to the models. This does
not guarantee a correct migration, so you will need to manually inspect the generated migration file to make sure
it is accurate. Be sure to make sure to remove any commands that are not related to the change you are making.

When adding a migration for SQLite it's important to include the following `PRAGMA` statements for both upgrade and downgrade

```python
def upgrade():
    op.execute("PRAGMA foreign_keys=OFF") # <-- add this line
    
    # migration code here
    
    op.execute("PRAGMA foreign_keys=ON") # <-- add this line


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF") # <-- add this line

    # migration code here
    
    op.execute("PRAGMA foreign_keys=ON") # <-- add this line

```

The new migration can be found in the `src/prefect/server/database/migrations/versions/` directory. Each database type
has its own subdirectory. For example, the SQLite migrations are stored in `src/prefect/server/database/migrations/versions/sqlite/`.

After you have inspected the migration file, you can apply the migration to your database by running the following command:

<div class="terminal">
```bash
prefect server database upgrade -y
```
</div>

Once you have successfully created and applied migrations for all database types, make sure to update `MIGRATION-NOTES.md`
to document your additions.
