[![CircleCI](https://circleci.com/gh/PrefectHQ/prefect/tree/master.svg?style=svg&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344)](https://circleci.com/gh/PrefectHQ/prefect/tree/master)

# Prefect

## Welcome to Prefect!

Prefect is a workflow management system designed for modern data infrastructures.

Users organize `tasks` into `flows`, and Prefect takes care of the rest!


### "...Prefect?"

From the Latin *praefectus*, meaning "one who is in charge", a prefect is an official who oversees a domain and ensures that the rules are followed.

It also happens to be the name of a roving researcher for that wholly remarkable book, *The Hitchhiker's Guide to the Galaxy*.


## Installation

### Requirements

Prefect requires Python 3.4+.

### Install
```
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
pip install .
```


## Development

### Install

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
conda env create
pip install -e .
```

### Unit Tests

```bash
cd prefect
pytest
```

## Documentation

To build and view documentation:
```bash
yarn docs:dev
```
This will automatically open a new browser window, but there will be a slight delay
while the initial build finishes. When it finishes, the browser will automatically
refresh.
