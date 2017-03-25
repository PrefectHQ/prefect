# Prefect

Prefect is a workflow manager.

## Instructions
*Don't Panic*


## Requirements

Prefect requires Python 3.5+

## Installation

To install Prefect for development:
```bash
git clone https://gitlab.com/jlowin/prefect.git
pip install -e ./prefect
```

## Unit Tests
To simply run tests (note some tests will require a database):
1. Execute: `pytest`

To run tests exactly as they are run in GitLab CI (including all databases and infrastructure):
1. Install the [GitLab CI Runner](https://docs.gitlab.com/runner/install/index.html)
1. Install [Docker](https://docs.docker.com/engine/installation/) and start the Docker Engine
1. Execute: `gitlab-runner exec docker test`
