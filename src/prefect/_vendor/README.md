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
