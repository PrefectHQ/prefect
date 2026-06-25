# filesystem

File path utilities, pathspec-based filtering, and local filesystem context managers.

## Purpose & Scope

Path normalization, file filtering compatible with `.gitignore`/`.prefectignore`-style pattern lists (`filter_files`), open-file-limit introspection (`get_open_file_limit`), and a `tmpchdir` context manager for scoped working-directory changes.

## Entry Points

- `filter_files(root, ignore_patterns, include_dirs=True) -> set[str]` — return the set of paths under `root` that should be *ignored* according to pathspec patterns. Intended as input to `shutil.copytree`'s `ignore` callback.
- `tmpchdir(path)` — context manager that `chdir`s into `path` and restores the previous cwd on exit.
- `get_open_file_limit() -> int` — platform-specific maximum open-file count, with a conservative Windows default.

## Pitfalls

- **`filter_files` with `include_dirs=True` (the default) always includes all ancestor directories of matched files**, even if those directories weren't directly matched by the ignore patterns. This ensures `shutil.copytree`'s `ignore_func` doesn't skip directories containing files that should be copied. Side effect: callers expecting only pathspec-matched entries will receive additional directory paths. The parent-dir expansion does NOT run when `include_dirs=False`.
