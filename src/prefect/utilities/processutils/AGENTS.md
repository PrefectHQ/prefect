# processutils

Subprocess execution, output streaming, command serialization, and signal forwarding.

## Purpose & Scope

Cross-platform subprocess primitives used by workers, runners, bundle execution, and the CLI. Handles process launch (`run_process`), output consumption (`consume_process_output`, `stream_text`), and platform-neutral command serialization (`command_to_string`, `command_from_string`).

## Entry Points

- `run_process(command, ...)` — async subprocess runner with output streaming and signal forwarding.
- `consume_process_output(process, stdout_sink, stderr_sink)` — drain a running process's streams into writers.
- `stream_text(source, *sinks)` — fan out a text stream to multiple sinks.
- `command_to_string(command: list[str]) -> str` / `command_from_string(s: str) -> list[str]` — platform-neutral serialize/deserialize of command arrays for storage and cross-platform bundles.
- `get_sys_executable() -> str` — `sys.executable` with platform-appropriate handling (see pitfalls).

## Pitfalls

- **Non-UTF-8 subprocess output is silently replaced.** `consume_process_output` and `stream_text` (via `TextReceiveStream(errors="replace")`) replace invalid bytes with the Unicode replacement character `\ufffd` rather than raising. If captured output contains `\ufffd`, the subprocess emitted bytes that were not valid UTF-8.
- **`command_to_string` always uses POSIX quoting (`shlex.join`), even on Windows.** This is intentional for platform-neutral storage — bundle commands are serialized by one platform and may be deserialized by another. `command_from_string` uses a dual-path approach: if the string was POSIX-serialized by Prefect (round-trips cleanly through `shlex.split`/`shlex.join`), it uses POSIX parsing; otherwise it falls back to native Windows command-line parsing (`CommandLineToArgvW`). Do not use `" ".join(command)` or `shlex.split(command)` directly when working with stored Prefect commands — use these helpers instead.
- **`get_sys_executable()` no longer quotes the Python path on Windows.** It previously returned `'"path/to/python"'` (with embedded quotes) on Windows; now it returns the raw path. Code relying on the old quoted form (e.g., joining into a shell string) will break — use `subprocess.list2cmdline` or `command_to_string` for shell-safe serialization instead.
