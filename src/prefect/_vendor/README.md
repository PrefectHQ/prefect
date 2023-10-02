# Vendored dependencies of `prefect`

## FastAPI, vendored from tiangolo/fastapi@0.103.2

We are temporarily vendoring `fastapi` to help us untangle `pydantic` requirements as we
gradually bring `pydantic>2` support to `prefect`.  FastAPI's compatibility layer
makes a strong assumption that having `pydantic>2` installed means that all of your
models are v2 models.  We will be adjusting that compatibility layer accordingly.

If we do need to update the version before we're done with it:

```
VERSION=0.103.2
rm -Rf /tmp/fastapi
git clone https://github.com/tiangolo/fastapi -b $VERSION /tmp/fastapi
rsync -ravdP /tmp/fastapi/fastapi/ src/prefect/_vendor/fastapi/
```

After syncing the files up, replace any internal references to `fastapi` within FastAPI
to refer to the module as `prefect._vendor.fastapi`.  So replace all:

* `import fastapi` -> `import prefect._vendor.fastapi`
* `from fastapi` -> `from prefect._vendor.fastapi`

Please also review `/tmp/fastapi/pyproject.toml` to review the `dependencies` section to
see if our versions need to be updated too.
