"""
Export commands for the EVOSEAL CLI.

This module provides commands for exporting data from the EVOSEAL system.
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from ..base import EVOSEALCommand

# Initialize the Typer app
app = typer.Typer(name="export", help="Export results/variants")

# Supported export formats and their file extensions
FORMAT_SUPPORT: dict[str, list[str]] = {
    "results": ["json", "csv"],
    "variants": ["json", "yaml"],
    "all": ["json", "yaml"],
}


@app.callback()
def main() -> None:
    """Export results and variants."""
    return None


@app.command("results")
def export_results(
    run_id: Annotated[
        str,
        typer.Argument(help="ID of the run to export."),
    ],
    output_file: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path. If not provided, prints to stdout.",
            dir_okay=False,
            writable=True,
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help=f"Output format: {', '.join(FORMAT_SUPPORT['results'])}.",
        ),
    ] = "json",
    include_metrics: Annotated[
        bool,
        typer.Option(
            "--metrics/--no-metrics",
            help="Include performance metrics in the export.",
        ),
    ] = True,
    include_code: Annotated[
        bool,
        typer.Option(
            "--code/--no-code",
            help="Include source code in the export.",
        ),
    ] = False,
) -> None:
    """Export results from a specific run."""
    if format.lower() not in FORMAT_SUPPORT["results"]:
        typer.echo(
            f"Unsupported format: {format}. Supported formats: {', '.join(FORMAT_SUPPORT['results'])}"
        )
        raise typer.Exit(1)

    # TODO: Implement actual results export
    results: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "completed",
        "metrics": (
            {
                "fitness": 0.85,
                "generations": 100,
                "best_score": 0.92,
            }
            if include_metrics
            else {}
        ),
        "code": ("# Sample code\ndef main():\n    print('Hello, World!')" if include_code else ""),
    }

    output: str = ""
    if format == "json":
        output = json.dumps(results, indent=2)
    elif format == "csv":
        # Simple CSV output for metrics
        import csv
        import io

        output_io = io.StringIO()
        writer = csv.writer(output_io)
        writer.writerow(["Metric", "Value"])
        if include_metrics:
            for k, v in results.get("metrics", {}).items():
                writer.writerow([k, v])
        output = output_io.getvalue()
    else:  # txt
        output = f"Run ID: {results['run_id']}\n"
        output += f"Status: {results['status']}\n"
        output += f"Timestamp: {results['timestamp']}\n"
        if include_metrics:
            output += "\nMetrics:\n"
            for k, v in results.get("metrics", {}).items():
                output += f"  {k}: {v}\n"
        if include_code and results.get("code"):
            output += "\nCode:\n"
            output += results["code"]

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)
        typer.echo(f"Results exported to {output_file}")
    else:
        typer.echo(output)


@app.command("variant")
def export_variant(
    variant_id: Annotated[
        str,
        typer.Argument(help="ID of the variant to export."),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory. If not provided, uses current directory.",
            file_okay=False,
            dir_okay=True,
            writable=True,
        ),
    ] = Path("."),
    include_dependencies: Annotated[
        bool,
        typer.Option(
            "--dependencies/--no-dependencies",
            help="Include dependency information in the export.",
        ),
    ] = True,
) -> None:
    """Export a specific code variant."""
    # TODO: Implement actual variant export
    output_dir = output_dir / f"variant_{variant_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create sample files
    (output_dir / "main.py").write_text(
        "# Sample variant code\ndef main():\n    print('Hello from variant!')"
    )

    if include_dependencies:
        (output_dir / "requirements.txt").write_text("numpy>=1.20.0\npandas>=1.3.0")

    typer.echo(f"Variant {variant_id} exported to {output_dir}")


@app.command("all")
def export_all(
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory. If not provided, uses current directory.",
            file_okay=False,
            dir_okay=True,
            writable=True,
        ),
    ] = Path("."),
    include_metrics: Annotated[
        bool,
        typer.Option(
            "--metrics/--no-metrics",
            help="Include performance metrics in the export.",
        ),
    ] = True,
    include_code: Annotated[
        bool,
        typer.Option(
            "--code/--no-code",
            help="Include source code in the export.",
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help=f"Output format: {', '.join(FORMAT_SUPPORT['all'])}.",
        ),
    ] = "json",
) -> None:
    """Export all data from the EVOSEAL system.

    Args:
        output_dir: Directory to export data to
        include_metrics: Whether to include performance metrics
        include_code: Whether to include source code
        format: Output format
    """
    if format.lower() not in FORMAT_SUPPORT["all"]:
        typer.echo(
            f"Unsupported format: {format}. Supported formats: {', '.join(FORMAT_SUPPORT['all'])}"
        )
        raise typer.Exit(1)

    # TODO: Implement actual export all
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create sample export structure
    (output_dir / "config.yaml").write_text("# Configuration\nproject: evoseal\nversion: 0.1.0")

    results_dir = output_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # Sample results
    results = [
        {"run_id": "run1", "fitness": 0.85, "generation": 100},
        {"run_id": "run2", "fitness": 0.92, "generation": 150},
    ]

    if format == "json":
        with open(results_dir / "results.json", "w") as f:
            json.dump({"results": results}, f, indent=2)
    elif format == "yaml":
        import yaml

        with open(results_dir / "results.yaml", "w") as f:
            yaml.dump({"results": results}, f, default_flow_style=False)
    elif format == "csv":
        import csv

        with open(results_dir / "results.csv", "w", newline="") as f:
            if results and isinstance(results, list) and len(results) > 0:
                fieldnames = list(results[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)

    typer.echo(f"All data exported to {output_dir}")


if __name__ == "__main__":
    app()
