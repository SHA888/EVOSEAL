# EVOSEAL Test Suite

## Test Structure

- **Unit tests** are located in `tests/unit/` and cover individual modules and classes.
- **Integration tests** are in `tests/integration/` and cover multi-component workflows.
- **Regression tests** are in `tests/regression/` and ensure bugs and invariants remain fixed.
- **Benchmarks** are in the `benchmarks/` directory and use `pytest-benchmark`.

## Running Tests

- Activate the virtual environment: `source .venv/bin/activate`
- Run all tests with coverage:
  ```sh
  pytest --cov=evoseal --cov-report=term-missing
  ```
- Run a specific test file:
  ```sh
  pytest tests/unit/agentic_system/test_agentic_system.py
  ```
- Run benchmarks:
  ```sh
  pytest benchmarks/
  ```

## Coverage & Reporting

- Coverage is measured with `pytest-cov`.
- Aim for high coverage, especially in critical modules (`evoseal/agentic_system.py`, `evoseal/seal_interface.py`, `integration/dgm/evolution_manager.py`).
- Use `--cov-report=term-missing` to see uncovered lines.
- Review edge cases and error paths for all DGM core components, not just main workflows.

## Mocking & Fixtures

- Use `unittest.mock.patch` to isolate tests from external APIs and side effects.
- Patch all major dependencies (e.g., Docker, Anthropic, OpenEvolve, SEAL providers) at the top of test files.
- Use pytest fixtures for temporary directories, sample data, and resource setup/teardown.
- Always mock file I/O and OS operations when testing error paths or edge cases.

## Advanced Test Strategies

- **Edge-case coverage:** Write tests for empty, malformed, or corrupted data (e.g., empty archives, invalid JSON, None/empty run IDs).
- **Error-path testing:** Simulate exceptions from dependencies (e.g., DGM_outer raising, data_adapter returning None, JSON decode errors) and verify correct propagation/handling.
- **Archive and group management:** Test duplicate, missing, or corrupted archive entries.
- **Pipeline integration:** Maintain integration tests that exercise the entire DGM workflow, including simulated failures and recovery.
- **Regression protection:** Add regression tests for previously fixed bugs and invariants.

## DGM Core Coverage Philosophy

- All core DGM components (`EvolutionManager`, `AgenticSystem`, `SEALInterface`) must have:
  - Unit tests for all public methods, including edge and error cases.
  - Mocking of all external APIs and dependencies.
  - Integration tests verifying multi-component interaction and pipeline correctness.
  - Regression tests to catch previously fixed issues.
- Test isolation is critical: never let external APIs, files, or network calls affect test outcomes.
- Document new test conventions, patterns, or strategies here as they evolve.

## Adding New Tests & Benchmarks

- Place new unit tests in the relevant `tests/unit/` subdirectory.
- Add integration or regression tests for new workflows or bug fixes.
- Write benchmarks using `pytest-benchmark` and put them in `benchmarks/`.
- Document new test conventions or patterns in this README.
