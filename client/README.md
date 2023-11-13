# Overview

This directory contains files for building and publishing the `prefect-client` 
library. `prefect-client` is built by removing source code from `prefect` and 
packages its own `requirements.txt` and `setup.py`. This process can happen 
in one of three ways:

- automatically whenever a PR is created (see 
`.github/workflows/prefect-client.yaml`)
- automatically whenever a Github release is published (see 
`.github/workflows/prefect-client-publish.yaml`)
- manually by running the `client/build_client.sh` script locally

Note that whenever a Github release is published the `prefect-client` will 
not only get built but will also be distributed to PyPI. `prefect-client` 
releases will have the same versioning as `prefect` - only the package names 
will be different.

This directory also includes a "minimal" flow that is used for smoke 
tests to ensure that the built `prefect-client` is functional.

In general, these builds, smoke tests, and publish steps should be transparent. 
It these automated steps fail, use the `client/build_client.sh` script to run 
the build and smoke test locally and iterate on a fix. The failures will likely 
be from:

- including a new dependency that is not installed in `prefect-client`
- re-arranging or adding files in such a way that a necessary file is rm'd at 
  build time
