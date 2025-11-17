use `gh` to read and understand the following github issue: $1.

Read the body and all comments in the issue.

before reproducing, `rg` for documentation in `docs/` that may be relevant to the issue.

if a `repros/` directory already exists (it will be locally gitignored), `rg` for relevant SDK usage to gain context.


To reproduce, create a file named by issue number (ie. `1234.py`) in a locally gitignored (.git/info/exclude) `repros/` directory with a minimal reproducible example that reproduces the issue. Because `repros/` is gitignored, you should NEVER reference it in a PR body, instead put the entire reproduction script in a python snippet inside a `<details>` tag.

If the reproduction requires external dependencies, use `uv` to inline script dependencies to install them like this:

```
# ///script
# dependencies = ["pandas", "numpy"]
# ///

# rest of script
```
and then invoke the script with `uv run --with-editable . repros/1234.py` to use the editable copy of Prefect along with the external dependencies.

Review the actual `prefect` library in `src/prefect` (or integration in `src/integrations`) to ensure that the reproduction is aware of the implementation details of the code.
