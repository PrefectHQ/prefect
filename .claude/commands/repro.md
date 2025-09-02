Use the github MCP (if available, use `gh` otherwise) to read and understand the following github issue: $1.

Read the body and all comments in the issue.

To reproduce, create a file named by issue number (ie. `1234.py`) in a locally gitignored (.git/info/exclude) `repros/` directory with a minimal reproducible example that reproduces the issue.

If the reproduction requires external dependencies, use uv inline script dependencies to install them like this:

```
# ///script
# dependencies = ["pandas", "numpy"]
# ///

# rest of script
```
and then invoke the script with `uv run --with-editable . repros/1234.py` to use the editable copy of Prefect along with the external dependencies.

Review the actual `prefect` library in `src/prefect` (or integration in `src/integrations`) to ensure that the reproduction is aware of the implementation details of the code.
