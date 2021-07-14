# Workflows

This folder contains workflows for CI

- test: Runs python tests on ubuntu-latest with python 3.7
- static_analysis: Runs mypy, black, flake8

## Testing locally

These workflows can be replicated locally using [`act`](https://github.com/nektos/act)

```bash
$ brew install act
$ act pull_request  --container-architecture linux/amd64
```

The container architecture flag is only necessary if using a Mac with a M1 chip