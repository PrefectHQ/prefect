---
description: Learn about contributing to Prefect.
tags:
    - open source
    - contributing
    - development
    - standards
    - migrations
---

# Contributing

Thanks for considering contributing to Prefect!

## Setting up a development environment

First, you'll need to download the source code and install an editable version of the Python package:

<div class="terminal">
```bash
# Clone the repository
git clone https://github.com/PrefectHQ/prefect.git
cd prefect

# We recommend using a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install the package with development dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks for required formatting
pre-commit install
```
</div>

If you don't want to install the pre-commit hooks, you can manually install the formatting dependencies with:

<div class="terminal">
```bash
pip install $(./scripts/precommit-versions.py)
```
</div>

You'll need to run `black`, `autoflake8`, and `isort` before a contribution can be accepted.

After installation, you can run the test suite with `pytest`:


<div class="terminal">
```bash
# Run all the tests
pytest tests


# Run a subset of tests
pytest tests/test_flows.py
```
</div>

!!! tip "Building the Prefect UI"
    If you intend to run a local Prefect server during development, you must first build the UI. See [UI development](#ui-development) for instructions.

!!! note "Windows support is under development"
    Support for Prefect on Windows is a work in progress.

    Right now, we're focused on your ability to develop and run flows and tasks on Windows, along with running the API server, orchestration engine, and UI.

    Currently, we cannot guarantee that the tooling for developing Prefect itself in a Windows environment is fully functional.



## Prefect Code of Conduct

### Our Pledge

In the interest of fostering an open and welcoming environment, we as
contributors and maintainers pledge to making participation in our project and
our community a harassment-free experience for everyone, regardless of age, body
size, disability, ethnicity, sex characteristics, gender identity and expression,
level of experience, education, socio-economic status, nationality, personal
appearance, race, religion, or sexual identity and orientation.

### Our Standards

Examples of behavior that contributes to creating a positive environment
include:

* Using welcoming and inclusive language
* Being respectful of differing viewpoints and experiences
* Gracefully accepting constructive criticism
* Focusing on what is best for the community
* Showing empathy towards other community members

Examples of unacceptable behavior by participants include:

* The use of sexualized language or imagery and unwelcome sexual attention or
  advances
* Trolling, insulting/derogatory comments, and personal or political attacks
* Public or private harassment
* Publishing others' private information, such as a physical or electronic
  address, without explicit permission
* Other conduct which could reasonably be considered inappropriate in a
  professional setting

### Our Responsibilities

Project maintainers are responsible for clarifying the standards of acceptable
behavior and are expected to take appropriate and fair corrective action in
response to any instances of unacceptable behavior.

Project maintainers have the right and responsibility to remove, edit, or
reject comments, commits, code, wiki edits, issues, and other contributions
that are not aligned to this Code of Conduct, or to ban temporarily or
permanently any contributor for other behaviors that they deem inappropriate,
threatening, offensive, or harmful.

### Scope

This Code of Conduct applies within all project spaces, and it also applies when
an individual is representing the project or its community in public spaces.
Examples of representing a project or community include using an official
project e-mail address, posting via an official social media account, or acting
as an appointed representative at an online or offline event. Representation of
a project may be further defined and clarified by project maintainers.

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported by contacting Chris White at [chris@prefect.io](mailto:chris@prefect.io). All
complaints will be reviewed and investigated and will result in a response that
is deemed necessary and appropriate to the circumstances. The project team is
obligated to maintain confidentiality with regard to the reporter of an incident.
Further details of specific enforcement policies may be posted separately.

Project maintainers who do not follow or enforce the Code of Conduct in good
faith may face temporary or permanent repercussions as determined by other
members of the project's leadership.

### Attribution

This Code of Conduct is adapted from the [Contributor Covenant][homepage], version 1.4,
available at [https://www.contributor-covenant.org/version/1/4/code-of-conduct.html](https://www.contributor-covenant.org/version/1/4/code-of-conduct.html)

[homepage]: https://www.contributor-covenant.org

For answers to common questions about this code of conduct, see
[https://www.contributor-covenant.org/faq](https://www.contributor-covenant.org/faq)

## Developer tooling

The Prefect CLI provides several helpful commands to aid development.

Start all services with hot-reloading on code changes (requires UI dependencies to be installed):

<div class="terminal">
```bash
prefect dev start
```
</div>

Start a Prefect API that reloads on code changes:

<div class="terminal">
```bash
prefect dev api
```
</div>

Start a Prefect agent that reloads on code changes:

<div class="terminal">
```bash
prefect dev agent
```
</div>

### UI development

Developing the Prefect UI requires that [npm](https://github.com/npm/cli) is installed.

Start a development UI that reloads on code changes:

<div class="terminal">
```bash
prefect dev ui
```
</div>

Build the static UI (the UI served by `prefect server start`):

<div class="terminal">
```bash
prefect dev build-ui
```
</div>

### Kubernetes development

Generate a manifest to deploy a development API to a local kubernetes cluster:

<div class="terminal">
```bash
prefect dev kubernetes-manifest
```
</div>

To access the Prefect UI running in a Kubernetes cluster, use the `kubectl port-forward` command to forward a port on your local machine to an open port within the cluster. For example:

<div class="terminal">
```bash
kubectl port-forward deployment/prefect-dev 4200:4200
```
</div>

This forwards port 4200 on the default internal loop IP for localhost to the Prefect server deployment.

To tell the local `prefect` command how to communicate with the Prefect API running in Kubernetes, set the `PREFECT_API_URL` environment variable:

<div class="terminal">
```bash
export PREFECT_API_URL=http://localhost:4200/api
```
</div>

Since you previously configured port forwarding for the localhost port to the Kubernetes environment, you’ll be able to interact with the Prefect API running in Kubernetes when using local Prefect CLI commands.

### Adding Database Migrations
To make changes to a table, first update the SQLAlchemy model in `src/prefect/server/database/orm_models.py`. For example,
if you wanted to add a new column to the `flow_run` table, you would add a new column to the `FlowRun` model:

```python
# src/prefect/server/database/orm_models.py

@declarative_mixin
class ORMFlowRun(ORMRun):
    """SQLAlchemy model of a flow run."""
    ...
    new_column = Column(String, nullable=True) # <-- add this line
```

Next, you will need to generate new migration files. You must generate a new migration file for each database type. 
Migrations will be generated for whatever database type `PREFECT_API_DATABASE_CONNECTION_URL` is set to. See [here](/concepts/database/#configuring-the-database)
for how to set the database connection URL for each database type.

To generate a new migration file, run the following command:

<div class="terminal">
```bash
prefect server database revision --autogenerate -m "<migration name>"
```
</div>

Try to make your migration name brief but descriptive. For example:

- `add_flow_run_new_column`
- `add_flow_run_new_column_idx`
- `rename_flow_run_old_column_to_new_column`

The `--autogenerate` flag will automatically generate a migration file based on the changes to the models. 
!!! warning "Always inspect the output of `--autogenerate`" 
    `--autogenerate` will generate a migration file based on the changes to the models. However, it is not perfect.
    Be sure to check the file to make sure it only includes the changes you want to make. Additionally, you may need to
    remove extra statements that were included and not related to your change.

When adding a migration for SQLite, it's important to include the following `PRAGMA` statements for both upgrade and downgrade:

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
