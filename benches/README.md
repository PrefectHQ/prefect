# Benchmarks

Benchmarks use `pytest-benchmark`.

To run, use `python benches`.

To run a subset of benchmarks, use `python benches <file>` e.g. `python benches bench_flows.py`

To run benchmarks with additional options, use `python benches --<option>=<value>` e.g. `python benches --min-rounds 2`

**WARNING**: Benchmarks do _not_ run against a temporary database by default. You must provide a target API or database or your current settings will be used.