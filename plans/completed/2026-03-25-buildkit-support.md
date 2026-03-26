# Docker BuildKit Support via python-on-whales

## Goal

Add opt-in BuildKit support to Prefect's Docker image building by introducing `python-on-whales` as an alternative build backend. Users who need BuildKit features (secrets, SSH forwarding, multi-platform builds, `--mount` syntax) can opt in via a `build_backend="buildx"` parameter while the default docker-py path remains unchanged.

## Non-Goals

1. Replacing docker-py entirely. It remains the default backend.
2. Changing container run/create/pull behavior in `DockerWorker` — only build and push are affected.
3. Supporting Podman or other container runtimes (even though python-on-whales supports them).

## Background

1. Prefect uses docker-py for all image building. docker-py has no BuildKit support — [docker/docker-py#2230](https://github.com/docker/docker-py/issues/2230) has been open for 6+ years.
2. Docker's legacy builder is deprecated since v23.0. Dockerfiles using `--mount` syntax fail entirely through docker-py.
3. Users cannot use build secrets safely — they must use build args, which are visible in image history.
4. [python-on-whales](https://github.com/gabrieldemarmiesse/python-on-whales) wraps the Docker CLI binary, providing full BuildKit/buildx support through a typed Python API. It is actively maintained (monthly releases) and used by Apache Airflow.
5. `prefect dev build-image` already shells out to the Docker CLI via subprocess, establishing precedent for CLI-based builds in this codebase.

## Architecture

Two build paths exist today, both using docker-py:

| Path | Entry point | Builds via |
|------|-------------|------------|
| **SDK** | `flow.deploy()` → `DockerImage.build()` | `dockerutils.build_image()` → `client.api.build()` |
| **YAML steps** | `prefect deploy` → `build_docker_image()` | `client.api.build()` directly |

This plan adds a parallel buildx path to both. A new module `src/prefect/docker/buildx.py` encapsulates all python-on-whales interactions. The existing code dispatches to it based on a `build_backend` parameter.

```
DockerImage(name="myimage", build_backend="buildx", platforms=["linux/amd64"])
    │
    ├── build_backend="docker-py" (default) ──→ dockerutils.build_image() ──→ docker-py
    │
    └── build_backend="buildx" ──→ buildx.build_image() ──→ python-on-whales ──→ docker CLI
```

## Dependency Strategy

`python-on-whales` is an **optional dependency**, not required for default operation:

- Add to `pyproject.toml` under a `buildx` extra: `buildx = ["python-on-whales>=0.81"]`
- Add to `prefect-docker`'s optional deps as well
- Runtime import guard in `buildx.py` — if the user sets `build_backend="buildx"` without installing the extra, raise a clear error with install instructions

## File Changes

### New file: `src/prefect/docker/buildx.py`

The python-on-whales backend module. Contains:

- `buildx_build_image(context, dockerfile, tag, pull, platform, stream_progress_to, push, **kwargs) -> str` — wraps `python_on_whales.docker.buildx.build()`. Returns the image ID (via `--iidfile`). Accepts buildx-native kwargs like `secrets`, `ssh`, `cache_from`, `cache_to`, `platforms`. When `push=True`, passes `--push` to buildx so the build-and-push happens in a single step (required for multi-platform builds where the result is a manifest list, not a local image).
- `buildx_push_image(name, tag, stream_progress_to) -> None` — wraps `python_on_whales.docker.image.push()`. Used when pushing a previously-built single-platform image.
- Import guard at module level that raises `ImportError` with install instructions if python-on-whales is missing.

Design notes:
- The `IMAGE_LABELS` (`{"io.prefect.version": ...}`) must be applied to buildx builds too, via the `labels` parameter.
- For multi-platform builds, `docker.buildx.build(push=True)` is the only viable path — buildx cannot load multi-platform results into the local daemon. When `platforms` has multiple entries and `push=False`, raise a clear error explaining this constraint.
- The retry logic from `dockerutils.build_image` should be reused. Factor the retry wrapper into a shared helper or have `buildx.build_image` implement its own.

### Modified: `src/prefect/docker/docker_image.py`

Add `build_backend: str = "docker-py"` parameter to `DockerImage.__init__`. Store as `self.build_backend`.

In `build()`:
- If `self.build_backend == "docker-py"`: existing path (call `build_image()` from dockerutils)
- If `self.build_backend == "buildx"`: call `buildx_build_image()` from the new module

In `push()`:
- If `self.build_backend == "docker-py"`: existing path
- If `self.build_backend == "buildx"`: call `buildx_push_image()`

Build-and-push optimization: When `build_backend="buildx"`, `DockerImage` should support a `push=True` kwarg in `build()` that passes `--push` to buildx, performing build and push as a single operation. This is required for multi-platform builds and more efficient for single-platform builds. When `push=True` is passed to `build()`, the subsequent `push()` call should be a no-op.

The `build_kwargs` passthrough changes meaning based on backend:
- `"docker-py"` → kwargs go to `docker-py`'s `client.api.build()`
- `"buildx"` → kwargs go to `python_on_whales.docker.buildx.build()`

Document this clearly in the `DockerImage` docstring and ensure invalid kwargs produce helpful errors.

### Modified: `src/integrations/prefect-docker/prefect_docker/deployments/steps.py`

Add `build_backend: str = "docker-py"` parameter to `build_docker_image()`.

When `build_backend="buildx"`:
- Import and call `buildx_build_image()` instead of `client.api.build()`
- `push_docker_image()` also gets a `build_backend` parameter — when `"buildx"`, use `buildx_push_image()` instead of docker-py's push

### Modified: `pyproject.toml`

Add optional extra:

```toml
[project.optional-dependencies]
buildx = ["python-on-whales>=0.81"]
```

### Modified: `src/integrations/prefect-docker/pyproject.toml`

Add optional extra:

```toml
[project.optional-dependencies]
buildx = ["python-on-whales>=0.81"]
```

## Testing Strategy

### Unit tests: `tests/docker/test_buildx.py` (new)

- Mock `python_on_whales` to test `buildx_build_image()` and `buildx_push_image()` without a Docker daemon
- Test that `IMAGE_LABELS` are passed through
- Test import guard raises helpful error when python-on-whales is not installed
- Test kwargs passthrough (secrets, ssh, platforms, cache_from, etc.)

### Unit tests: `tests/docker/test_docker_image.py` (modify)

- Add tests for `DockerImage(build_backend="buildx")` dispatching to `buildx_build_image`
- Test that `build_kwargs` are forwarded correctly for both backends
- Test invalid `build_backend` value raises `ValueError`

### Unit tests: `src/integrations/prefect-docker/tests/deployments/test_steps.py` (modify)

- Add parameterized tests for `build_docker_image(build_backend="buildx")`
- Verify dispatch to `buildx_build_image` with correct kwargs

### Service tests: `tests/docker/test_image_builds.py` (modify)

- Add `@pytest.mark.service("docker")` tests that build a real image via the buildx backend
- Verify image ID is returned, tags are applied, progress is streamed

## Rollout

1. **Phase 1**: Ship as opt-in with `build_backend="buildx"`. Default remains `"docker-py"`. Document in deployment docs.
2. **Phase 2**: After user validation, consider making `"buildx"` the default when python-on-whales is installed (auto-detect).
3. **Phase 3**: If docker-py's legacy builder path is eventually removed by Docker, migrate the default to buildx and deprecate the docker-py backend.

## Resolved Decisions

1. **No Prefect setting for `build_backend`** — keep it parameter-only for now. A `PREFECT_DOCKER_BUILD_BACKEND` setting can be added in a follow-up if there's demand.
2. **Build-and-push in one step** — yes. The buildx backend supports `push=True` in `build()` to run `docker buildx build --push`. This is required for multi-platform builds and more efficient for single-platform.
3. **Version floor**: `python-on-whales>=0.81` (current latest release).
