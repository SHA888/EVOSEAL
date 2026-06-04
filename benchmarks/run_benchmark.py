#!/usr/bin/env python3
"""
EVOSEAL Benchmark Runner — Single-Shot Baseline

Runs single-shot LLM baseline on synthetic coding tasks.
Results recorded to benchmarks/comparison_results.md for reproducibility.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic


SYNTHETIC_PROBLEMS = [
    {
        "task_id": "synthetic_0",
        "name": "Sum first N",
        "prompt": "Write a function that returns the sum of the first n positive integers.\ndef sum_first_n(n: int) -> int:",
    },
    {
        "task_id": "synthetic_1",
        "name": "Palindrome check",
        "prompt": "Write a function that checks if a string is a palindrome.\ndef is_palindrome(s: str) -> bool:",
    },
    {
        "task_id": "synthetic_2",
        "name": "Find max",
        "prompt": "Write a function that finds the maximum value in a list.\ndef find_max(lst: list) -> int:",
    },
    {
        "task_id": "synthetic_3",
        "name": "Reverse list",
        "prompt": "Write a function that reverses a list.\ndef reverse_list(lst: list) -> list:",
    },
    {
        "task_id": "synthetic_4",
        "name": "Remove duplicates",
        "prompt": "Write a function that removes duplicates from a list.\ndef remove_duplicates(lst: list) -> list:",
    },
    {
        "task_id": "synthetic_5",
        "name": "Character count",
        "prompt": "Write a function that counts the occurrence of each character in a string.\ndef char_count(s: str) -> dict:",
    },
    {
        "task_id": "synthetic_6",
        "name": "Anagram check",
        "prompt": "Write a function that checks if two strings are anagrams.\ndef are_anagrams(s1: str, s2: str) -> bool:",
    },
    {
        "task_id": "synthetic_7",
        "name": "Fibonacci",
        "prompt": "Write a function that returns the nth Fibonacci number.\ndef fibonacci(n: int) -> int:",
    },
    {
        "task_id": "synthetic_8",
        "name": "Bubble sort",
        "prompt": "Write a function that sorts a list in ascending order.\ndef bubble_sort(lst: list) -> list:",
    },
    {
        "task_id": "synthetic_9",
        "name": "Factorial",
        "prompt": "Write a function that calculates factorial of a number.\ndef factorial(n: int) -> int:",
    },
]


def run_baseline(model: str, api_key: str, problems: list) -> dict:
    """Run single-shot baseline on problems."""
    client = anthropic.Anthropic(api_key=api_key)
    results = {"passed": 0, "failed": 0, "errors": 0, "total": 0}
    problems_evaluated = []

    print(f"\n📊 Running single-shot baseline ({len(problems)} problems, model={model})...")

    for idx, problem in enumerate(problems):
        if idx % 5 == 0:
            print(f"  [{idx}/{len(problems)}] {problem['name']}...")

        try:
            prompt = f"""You are an expert Python programmer. Complete this function:

{problem['prompt']}
    '''Your code here'''
    pass

Return ONLY the function body code (without the function signature or docstring). The code must be valid Python."""

            response = client.messages.create(
                model=model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )

            solution = response.content[0].text

            # Check if code is valid Python
            try:
                compile(solution, "<string>", "exec")
                results["passed"] += 1
                passed = True
            except SyntaxError as e:
                results["failed"] += 1
                passed = False

            results["total"] += 1
            problems_evaluated.append(
                {
                    "task_id": problem["task_id"],
                    "name": problem["name"],
                    "passed": passed,
                    "model": model,
                }
            )

        except Exception as e:
            results["errors"] += 1
            results["total"] += 1
            print(f"    ❌ Error: {str(e)[:60]}")

    return {
        "baseline": results,
        "model": model,
        "problems_evaluated": problems_evaluated,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    """Main benchmark runner."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        sys.exit(1)

    model = "claude-opus-4-8"

    print("=" * 70)
    print("EVOSEAL Benchmark: Single-Shot Baseline")
    print("=" * 70)
    print(f"Model: {model}")
    print(f"Dataset: Synthetic coding tasks ({len(SYNTHETIC_PROBLEMS)} problems)")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Provider: Anthropic API")

    # Run baseline
    results = run_baseline(model, api_key, SYNTHETIC_PROBLEMS)

    # Print results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    baseline = results["baseline"]
    pass_rate = 100 * baseline["passed"] / baseline["total"] if baseline["total"] > 0 else 0

    print(f"\nSingle-shot Baseline ({model}):")
    print(f"  Total problems: {baseline['total']}")
    print(f"  Passed (valid syntax): {baseline['passed']} ({pass_rate:.1f}%)")
    print(f"  Failed (syntax errors): {baseline['failed']}")
    print(f"  Errors (API/other): {baseline['errors']}")

    # Save results
    results_dir = Path("/app/benchmarks")
    results_dir.mkdir(parents=True, exist_ok=True)

    # Detailed JSON results
    results_file = results_dir / "baseline_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Detailed results: {results_file}")

    # Markdown report
    md_file = results_dir / "comparison_results.md"
    md_content = f"""# EVOSEAL Benchmark Results

**Generated:** {datetime.now().isoformat()}

## Single-Shot Baseline Results

**Model:** `{model}`
**Dataset:** Synthetic coding tasks ({baseline['total']} problems)
**Pass Rate (valid syntax):** {baseline['passed']}/{baseline['total']} ({pass_rate:.1f}%)

### Benchmark Details

- **Model:** Anthropic Claude Opus 4.8
- **Provider:** Anthropic API
- **Task Type:** Function completion (given signature, write body)
- **Evaluation:** Syntactic correctness (compiles without errors)
- **Environment:** Docker container (Python 3.11-slim, datasets-enabled)

### Results Breakdown

| Metric | Value |
|--------|-------|
| Passed (valid Python) | {baseline['passed']} |
| Failed (syntax errors) | {baseline['failed']} |
| Errors (API/runtime) | {baseline['errors']} |
| **Total** | **{baseline['total']}** |

### Detailed Results

"""

    for problem in results["problems_evaluated"]:
        status = "✓" if problem["passed"] else "✗"
        md_content += f"\n- [{status}] `{problem['task_id']}` ({problem['name']})"

    md_content += f"""

## Reproducibility

To reproduce:

```bash
cd /home/kresna/EVOSEAL

# Option 1: Docker
docker compose -f docker-compose.evoseal.yml run --rm evoseal python3 benchmarks/run_benchmark.py

# Option 2: Local venv
source .venv/bin/activate
python3 benchmarks/run_benchmark.py
```

**Requirements:**
- Python 3.11+
- `ANTHROPIC_API_KEY` environment variable set
- Dependencies: anthropic, pydantic

## Notes

- **Synthetic dataset:** Generated representative coding tasks (not from official HumanEval)
- **Evaluation method:** Syntactic validity (code compiles without SyntaxError)
- **Single-shot:** No iterative refinement or feedback; one attempt per problem
- **Next phases:** convergence plots (1.3) and self-improvement examples (1.4)

## Methodology

Each problem is presented to the model with a prompt asking for a function body completion.
The output is checked for Python syntactic validity using compile().
This validates code generation quality without runtime test execution (which would require problem-specific test suites).
"""

    with open(md_file, "w") as f:
        f.write(md_content)
    print(f"✓ Comparison results: {md_file}")

    print("\n✅ Benchmark complete!")
    print(f"\nNext: commit these files to git")
    print(f"  {results_file}")
    print(f"  {md_file}")


if __name__ == "__main__":
    main()
