"""System health check command for EVOSEAL.

Validates configuration, dependencies, API keys, and environment state.
Exits with non-zero only on critical failures (as defined in threat model and cost spec).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="doctor",
    help="Validate EVOSEAL system health and configuration",
    invoke_without_command=True,
)
console = Console()


def get_safety_yaml_path() -> Path:
    """Get the path to the safety configuration file."""
    return Path.cwd() / "configs" / "safety.yaml"


def get_budget_config_path() -> Path:
    """Get the path to the budget configuration file."""
    return Path.cwd() / ".claude" / "state" / "budget_snapshot.json"


def check_api_keys() -> tuple[bool, str]:
    """Check if API keys are configured and accessible.

    Returns:
        Tuple of (success, message)
    """
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if anthropic_key or openai_key:
        if anthropic_key:
            return True, "ANTHROPIC_API_KEY configured"
        else:
            return True, "OPENAI_API_KEY configured"
    else:
        return False, "No API keys found (ANTHROPIC_API_KEY or OPENAI_API_KEY required)"


def check_safety_yaml() -> tuple[bool, str]:
    """Check if safety.yaml exists and is well-formed.

    Returns:
        Tuple of (success, message)
    """
    safety_file = get_safety_yaml_path()

    if not safety_file.exists():
        return False, f"safety.yaml not found at {safety_file}"

    try:
        with open(safety_file) as f:
            config = yaml.safe_load(f)
        if config is None:
            return False, "safety.yaml is empty"
        return True, f"safety.yaml well-formed ({len(config)} keys)"
    except yaml.YAMLError as e:
        return False, f"safety.yaml malformed: {e}"
    except OSError as e:
        return False, f"Cannot read safety.yaml: {e}"


def check_dependencies() -> tuple[bool, str]:
    """Check if required Python dependencies are installed.

    Returns:
        Tuple of (success, message)
    """
    required_modules = [
        "typer",
        "structlog",
        "yaml",
        "pydantic",
        "asyncio",
    ]

    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)

    if missing:
        return False, f"Missing dependencies: {', '.join(missing)}"
    return True, "All required dependencies installed"


def check_git_state() -> tuple[bool, str]:
    """Check if Git repository is in a clean, valid state.

    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            return False, "Not in a git repository"

        # Check for uncommitted changes (warning, not critical)
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.stdout.strip():
            return True, "Git state OK (with uncommitted changes)"

        return True, "Git repository clean"
    except subprocess.TimeoutExpired:
        return False, "Git command timed out"
    except FileNotFoundError:
        return False, "Git not installed or not in PATH"
    except Exception as e:
        return False, f"Error checking git state: {e}"


def check_budget_config() -> tuple[bool, str]:
    """Check if budget configuration is valid per cost spec (2.8).

    Returns:
        Tuple of (success, message)
    """
    budget_file = get_budget_config_path()
    if not budget_file.exists():
        return True, "Budget config not yet created (optional, will be auto-generated)"

    try:
        with open(budget_file) as f:
            budget_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        error_type = "malformed JSON" if isinstance(e, json.JSONDecodeError) else "read error"
        return False, f"Budget config {error_type}: {e}"

    required = ["max_tokens_per_run", "max_cost_per_run"]
    missing = [f for f in required if f not in budget_data]
    if missing:
        return False, f"Budget config missing: {', '.join(missing)}"

    tokens, cost = budget_data["max_tokens_per_run"], budget_data["max_cost_per_run"]
    if tokens <= 0 or cost <= 0:
        invalid = "tokens" if tokens <= 0 else "cost"
        return False, f"max_{invalid}_per_run must be positive"

    return True, f"Budget config valid (max {tokens} tokens)"


@app.callback(invoke_without_command=True)
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output for each check",
    ),
) -> None:
    """Validate EVOSEAL system health and configuration.

    Checks:
    - API keys (ANTHROPIC_API_KEY or OPENAI_API_KEY)
    - configs/safety.yaml well-formedness
    - Required Python dependencies
    - Git repository state
    - Budget/cost configuration

    Exits with status 0 if all critical checks pass, non-zero on critical failures.
    """
    # Run all checks
    checks = [
        ("API Keys", check_api_keys),
        ("Safety Configuration", check_safety_yaml),
        ("Dependencies", check_dependencies),
        ("Git State", check_git_state),
        ("Budget Configuration", check_budget_config),
    ]

    results = []
    critical_failures = []

    for name, check_fn in checks:
        try:
            success, message = check_fn()
            results.append((name, success, message))
            if not success:
                # Determine if this is critical
                # Critical: API keys, safety.yaml, git state
                # Non-critical: budget config (will be auto-generated)
                if name in ["API Keys", "Safety Configuration", "Git State"]:
                    critical_failures.append((name, message))
        except Exception as e:
            results.append((name, False, f"Error: {e}"))
            if name in ["API Keys", "Safety Configuration", "Git State"]:
                critical_failures.append((name, str(e)))

    # Display results
    console.print()
    console.print("[bold]EVOSEAL System Health Check[/bold]")
    console.print()

    # Create results table
    results_table = Table(title="Validation Results", show_header=True)
    results_table.add_column("Check", style="cyan")
    results_table.add_column("Status", justify="right")
    results_table.add_column("Details", style="dim")

    for name, success, message in results:
        status = "[green]✓[/green]" if success else "[red]✗[/red]"
        results_table.add_row(name, status, message)

    console.print(results_table)
    console.print()

    # Summary
    total_checks = len(results)
    passed_checks = sum(1 for _, success, _ in results if success)

    console.print("[bold]Summary[/bold]")
    console.print(f"Checks passed: {passed_checks}/{total_checks}")

    if critical_failures:
        console.print("[bold red]Critical failures found:[/bold red]")
        for name, message in critical_failures:
            console.print(f"  • {name}: {message}")
        console.print()
        console.print("[dim]Run 'evoseal doctor --verbose' for details[/dim]")
        raise typer.Exit(code=1)
    else:
        console.print("[bold green]All critical checks passed[/bold green]")
        console.print()
