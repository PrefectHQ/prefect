# Code Style
- use complete and modern python typing (e.g. prefer `list[int]` over `List[int]`, `T | None` over `Optional[T]`)
- hide implementation details in private methods or modules
- do not change the public API of any module, class, or function

# Tests
- run `uv run pytest tests/some_file.py -k some_test_substr` to run a single test
- run `uv run pytest -n4` to run all tests in parallel with 4 processes

# Working on an issue
- write repros in a git-excluded directory, name the folder/file by issue number (e.g. `repros/1234.py`)
- reproduce the issue before making changes to the library
- once reproduced, change the library and use the repro to verify the issue is fixed
- if pertinent, find the appropriate place for a unit test and add one
- open a PR according to the PR style below

# PR Style
- start with "closes #1234" if the PR resolves an issue
- follow with "this PR {itemized summary of important changes}"
- put details in a `<details>` tag
- include markdown links to any relevant issues, discussions, docs, or other resources
