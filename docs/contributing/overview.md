---
description: Learn about contributing to Prefect 2.
tags:
    - open source
    - contributing
    - development
    - standards
---

# Contributing

Thanks for considering contributing to Prefect!

## Setting up a development environment

First, you'll need to download the source code and install an editable version of the Python package:

<div class="terminal">
```bash
# Clone the repository and switch to the 'orion' branch
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
git checkout orion
# Install the package with development dependencies
pip install -e ".[dev]"
# Setup pre-commit hooks for required formatting
pre-commit install
# Run tests
pytest
```
</div>

If you don't want to install the pre-commit hooks, you can manually install the formatting dependencies with:

<div class="terminal">
```bash
pip install $(./scripts/precommit-versions.py)
```
</div>

You'll need to run `black`, `autoflake8`, and `isort` before a contribution can be accepted.

!!! tip "Building the Prefect UI"
    If you intend to run a local Prefect Orion server during development, you must first build the UI. See [UI development](#ui-development) for instructions.

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

The Orion CLI provides several helpful CLI commands to aid development.

Start all services with hot-reloading on code changes (requires UI dependencies to be installed):

<div class="terminal">
```bash
prefect dev start
```
</div>

Start an Orion API that reloads on code changes:

<div class="terminal">
```bash
prefect dev api
```
</div>

Start an Orion agent that reloads on code changes:

<div class="terminal">
```bash
prefect dev agent
```
</div>

### UI development

Developing the Orion UI requires that [npm](https://github.com/npm/cli) is installed.

Start a development UI that reloads on code changes:

<div class="terminal">
```bash
prefect dev ui
```
</div>

Build the static UI (the UI served by `prefect orion start`):

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

To access the Orion UI running in a Kubernetes cluster, use the `kubectl port-forward` command to forward a port on your local machine to an open port within the cluster. For example:

<div class="terminal">
```bash
kubectl port-forward deployment/orion 4200:4200
```
</div>

This forwards port 4200 on the default internal loop IP for localhost to the “orion” deployment.

To tell the local `prefect` command how to communicate with the Orion API running in Kubernetes, set the `PREFECT_API_URL` environment variable:

<div class="terminal">
```bash
export PREFECT_API_URL=http://localhost:4200/api
```
</div>

Since you previously configured port forwarding for the localhost port to the Kubernetes environment, you’ll be able to interact with the Orion API running in Kubernetes when using local Prefect CLI commands.

