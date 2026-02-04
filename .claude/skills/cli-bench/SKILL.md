---
name: cli-bench
description: Benchmark Prefect CLI performance. Use when working on CLI startup time, import optimization, or evaluating CLI changes.
---

# CLI Benchmarking

Use [python-cli-bench](https://github.com/zzstoatzz/python-cli-bench) for CLI performance analysis.

## Setup

```bash
uv sync --group cli-bench
```

## Configuration

Benchmarks are configured in `benches/cli-bench.toml`:

```toml
[project]
name = "prefect"
import_path = "prefect.cli"
version_module = "prefect"

[[commands]]
name = "prefect --help"
args = ["prefect", "--help"]
category = "startup"
```

## Commands

### Run benchmarks

```bash
# run all benchmarks
uv run cli-bench -C benches/cli-bench.toml run

# run specific category
uv run cli-bench -C benches/cli-bench.toml run --category startup

# save baseline for comparison
uv run cli-bench -C benches/cli-bench.toml run -o baseline.json

# compare against baseline (with Welch's t-test)
uv run cli-bench -C benches/cli-bench.toml run -c baseline.json
```

### Analyze imports

```bash
# show import time breakdown
uv run cli-bench -C benches/cli-bench.toml imports

# show top 50 slowest imports
uv run cli-bench -C benches/cli-bench.toml imports --top 50
```

### Profile execution

```bash
# pyinstrument call tree
uv run cli-bench -C benches/cli-bench.toml profile
```

## CI Integration

Benchmarks run automatically on PRs via `.github/workflows/benchmarks.yaml`. Results are posted as PR comments with statistical comparison.

## When to Add Benchmarks

Add new `[[commands]]` entries to `benches/cli-bench.toml` when:
- Adding new CLI commands that should be fast
- Investigating specific command performance
- Establishing baselines for optimization work

## Related Resources

- Linear: CLI Performance Enhancements project
- `sandbox/cli-performance-direction.md` - strategic direction notes
- `sandbox/cli-import-spike/` - cyclopts vs typer benchmarks
- PR #20448 - LazyTyperGroup lazy loading work
