# EVOSEAL Benchmarks

## Purpose

Performance benchmarks for core evolutionary algorithms and system components.

## Running Benchmarks

Install pytest-benchmark:
```bash
pip install pytest-benchmark
```

Run all benchmarks:
```bash
pytest benchmarks/ --benchmark-only
```

## Writing Benchmarks

- Use the `benchmark` fixture from pytest-benchmark.
- Patch all external dependencies to isolate the code under test.
- See `test_evolution_benchmark.py` for an example.

## Location

Benchmarks are kept in this `/benchmarks` directory at the project root for easy discovery and separation from regular tests.
