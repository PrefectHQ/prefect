# filesystem

File path utilities, pathspec-based filtering, and local filesystem context managers.

## Purpose & Scope

Path normalization, file filtering compatible with `.gitignore`/`.prefectignore`-style pattern lists (`filter_files`), open-file-limit introspection (`get_open_file_limit`), and a `tmpchdir` context manager for scoped working-directory changes.

## Entry Points

- `filter_files(root, ignore_patterns, include_dirs=True, *, as_posix=False) -> set[str]` — return the set of included paths under `root` according to pathspec patterns. Returned paths are relative to `root` and use platform-native separators by default. Callers comparing against `Path.as_posix()` must opt in with `as_posix=True`. Used to build `shutil.copytree`'s `ignore` callback.
- `tmpchdir(path)` — changes the working directory and restores it on exit. Contexts nest on the same thread and serialize across threads that call `tmpchdir`.
- `get_open_file_limit() -> int` — platform-specific maximum open-file count, with a conservative Windows default.

## Pitfalls

- **`tmpchdir` changes the working directory for the entire process.** Other threads and async tasks can resolve relative paths against the temporary directory while the context is open. Use explicit paths or a subprocess `cwd` when concurrent work needs different base directories.
- **`filter_files` with `include_dirs=True` (the default) always includes all ancestor directories of matched files**, even if those directories weren't directly matched by the ignore patterns. This ensures `shutil.copytree`'s `ignore_func` doesn't skip directories containing files that should be copied. Side effect: callers expecting only pathspec-matched entries will receive additional directory paths. The parent-dir expansion does NOT run when `include_dirs=False`.
