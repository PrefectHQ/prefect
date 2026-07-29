# Run untrusted code in isolated sandboxes with `prefect-sandbox`

`prefect-sandbox` runs commands and model-generated code in disposable Docker
Sandboxes microVMs without forwarding the Prefect worker's environment.

See the [prefect-sandbox documentation](https://docs.prefect.io/integrations/prefect-sandbox)
for installation, usage, and security details.

## Try the same flow on either backend

From this directory:

```bash
uv sync

# Local Docker Sandboxes microVM (requires `sbx login` and `sbx policy ls`)
uv run python examples/hello_sandbox.py sbx

# Hosted Islo microVM
ISLO_API_KEY=isk_... uv run python examples/hello_sandbox.py islo
```

Both commands upload and execute the same Python file with outbound network access
denied, print the guest kernel, and destroy the microVM. See the
[complete flow](https://github.com/PrefectHQ/prefect/blob/main/src/integrations/prefect-sandbox/examples/hello_sandbox.py).
