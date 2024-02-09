# Vendored dependencies of `prefect`

## FastAPI, vendored from tiangolo/fastapi@0.99.1

We are temporarily vendoring `fastapi` to help us untangle `pydantic` requirements as we
gradually bring `pydantic>2` support to `prefect`.  FastAPI's compatibility layer
makes a strong assumption that having `pydantic>2` installed means that all of your
models are v2 models.  We will be adjusting that compatibility layer accordingly.

If we do need to change the version before we're done with it:

```
./src/prefect/_vendor/vendor-fastapi 0.99.1
```

Please also review `/tmp/fastapi/pyproject.toml` to review the `dependencies` section to
see if our versions need to be updated too.

## Starlette, vendored from encode/starlette@0.33.0

We are temporarily vendoring `starlette` as a dependency of our vendored `fastapi`.
While we originally just needed to pin our `starlette` to a version that was compatible
with `fastapi@0.99.1`, we can no longer do that due to a [published
CVE](https://github.com/advisories/GHSA-93gm-qmq6-w238) with `starlette<0.36.2`.  The
change in that version is simply to set a lower-bound on `python-multipart`, which we
have also done in `requirements-client.txt`

We can remove our vendored FastAPI and Starlette and move to the latest version after
the deprecation period for pydantic v1 support has passed.
