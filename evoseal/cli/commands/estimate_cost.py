"""Cost estimation commands for the EVOSEAL CLI.

Provides commands to estimate token consumption and costs for evolution runs
based on configurable parameters and cost models.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="estimate-cost",
    help="Estimate evolution costs",
    invoke_without_command=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    iterations: int = typer.Option(
        10, "--iterations", "-i", help="Number of evolution iterations to estimate"
    ),
    dgm_tokens_per_call: int = typer.Option(
        4000,
        "--dgm-tokens-per-call",
        help="Average tokens per DGM generation call",
    ),
    seal_tokens_per_cycle: int = typer.Option(
        100, "--seal-tokens-per-cycle", help="Tokens for SEAL data collection per cycle"
    ),
    seal_tokens_per_epoch: int = typer.Option(
        10000, "--seal-tokens-per-epoch", help="Tokens for one SEAL fine-tuning epoch"
    ),
    training_check_interval: int = typer.Option(
        10,
        "--training-check-interval",
        help="Cycles between fine-tuning checkpoints",
    ),
    cost_per_1k_tokens: float = typer.Option(
        0.005, "--cost-per-1k-tokens", help="Cost per 1000 tokens (e.g., 0.005 = $0.005)"
    ),
) -> None:
    """Estimate token consumption and costs for N evolution iterations.

    Calculates projected token usage based on:
    - DGM generation calls (variant generation)
    - SEAL token collection (per cycle)
    - Fine-tuning epochs (triggered at intervals)

    Example:
        evoseal estimate-cost --iterations 100 --dgm-tokens-per-call 4000
    """
    # Calculate base cycle costs
    dgm_cost_per_cycle = dgm_tokens_per_call  # One DGM call per cycle
    seal_cost_per_cycle = seal_tokens_per_cycle

    # Calculate total tokens for all cycles
    total_dgm_tokens = iterations * dgm_cost_per_cycle
    total_seal_cycle_tokens = iterations * seal_cost_per_cycle

    # Calculate fine-tuning epochs and costs
    epochs_triggered = max(1, iterations // training_check_interval)
    total_seal_finetuning_tokens = epochs_triggered * seal_tokens_per_epoch

    # Total token consumption
    total_tokens = total_dgm_tokens + total_seal_cycle_tokens + total_seal_finetuning_tokens

    # Calculate costs
    dgm_cost = (total_dgm_tokens * cost_per_1k_tokens) / 1000
    seal_cycle_cost = (total_seal_cycle_tokens * cost_per_1k_tokens) / 1000
    seal_finetuning_cost = (total_seal_finetuning_tokens * cost_per_1k_tokens) / 1000
    total_cost = dgm_cost + seal_cycle_cost + seal_finetuning_cost

    # Display results
    typer.echo()
    typer.echo("Cost Estimation Report")
    typer.echo(f"Iterations: {iterations}")
    typer.echo()

    # Breakdown table
    breakdown_table = Table(title="Token Consumption Breakdown", show_header=True)
    breakdown_table.add_column("Component", style="cyan")
    breakdown_table.add_column("Tokens", justify="right")
    breakdown_table.add_column("Cost", justify="right")
    breakdown_table.add_column("% of Total", justify="right")

    dgm_percent = (total_dgm_tokens / total_tokens * 100) if total_tokens > 0 else 0
    seal_cycle_percent = (total_seal_cycle_tokens / total_tokens * 100) if total_tokens > 0 else 0
    seal_finetuning_percent = (
        (total_seal_finetuning_tokens / total_tokens * 100) if total_tokens > 0 else 0
    )

    breakdown_table.add_row(
        "DGM (variant generation)",
        f"{total_dgm_tokens:,}",
        f"${dgm_cost:.4f}",
        f"{dgm_percent:.1f}%",
    )
    breakdown_table.add_row(
        "SEAL (per-cycle data collection)",
        f"{total_seal_cycle_tokens:,}",
        f"${seal_cycle_cost:.4f}",
        f"{seal_cycle_percent:.1f}%",
    )
    breakdown_table.add_row(
        f"SEAL (fine-tuning: {epochs_triggered} epochs)",
        f"{total_seal_finetuning_tokens:,}",
        f"${seal_finetuning_cost:.4f}",
        f"{seal_finetuning_percent:.1f}%",
    )
    breakdown_table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_tokens:,}[/bold]",
        f"[bold]${total_cost:.4f}[/bold]",
        "[bold]100.0%[/bold]",
    )

    console.print(breakdown_table)
    console.print()

    # Summary
    console.print("[bold]Summary[/bold]")
    console.print(f"Total tokens: [green]{total_tokens:,}[/green]")
    console.print(f"Total cost: [green]${total_cost:.4f}[/green]")
    if iterations > 0:
        console.print(
            f"Average per iteration: [yellow]{total_tokens / iterations:,.0f}[/yellow] tokens, [yellow]${total_cost / iterations:.6f}[/yellow]"
        )

    console.print()
    console.print("[dim]Note: Costs assume honest-but-fallible LLM output.[/dim]")
    console.print(
        f"[dim]Estimates based on cost model: ${cost_per_1k_tokens:.4f} per 1k tokens[/dim]"
    )
    console.print()
