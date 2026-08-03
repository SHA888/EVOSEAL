"""
Export commands for the EVOSEAL CLI.

This module provides commands for exporting data from the EVOSEAL system.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from evoseal.core.experiment_database import ExperimentDatabase

# Initialize the Typer app
app = typer.Typer(name="export", help="Export results/variants")

# Default database path (relative to CWD — callers must run from project root)
DEFAULT_DB_PATH = Path(".evoseal/experiments.db")

# Artifact types considered "dependency" artifacts (e.g. requirements.txt).
# When include_dependencies=False, these are excluded from variant exports.
DEPENDENCY_ARTIFACT_TYPES = {"dependency", "requirements"}

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

    if not DEFAULT_DB_PATH.exists():
        typer.echo(f"Error: No experiment database found at {DEFAULT_DB_PATH}")
        typer.echo("Run an evolution cycle first to generate data.")
        raise typer.Exit(1)

    try:
        db = ExperimentDatabase(DEFAULT_DB_PATH)
    except Exception as e:
        typer.echo(f"Error reading experiment database: {e}")
        raise typer.Exit(1) from None

    try:
        try:
            experiment = db.get_experiment(run_id)
        except Exception as e:
            typer.echo(f"Error querying experiment database: {e}")
            raise typer.Exit(1) from None

        if experiment is None:
            typer.echo(f"Error: No experiment found with ID '{run_id}'")
            typer.echo("Use 'evoseal status' to see available experiments.")
            raise typer.Exit(1)

        results: dict[str, Any] = {
            "run_id": experiment.id,
            "name": experiment.name,
            "description": experiment.description,
            "status": experiment.status.value,
            "created_at": experiment.created_at.isoformat(),
            "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
            "completed_at": experiment.completed_at.isoformat()
            if experiment.completed_at
            else None,
        }

        if experiment.result:
            results["result"] = {
                "best_fitness": experiment.result.best_fitness,
                "generations_completed": experiment.result.generations_completed,
                "total_evaluations": experiment.result.total_evaluations,
                "convergence_iteration": experiment.result.convergence_iteration,
                "execution_time": experiment.result.execution_time,
                "error_message": experiment.result.error_message,
            }

        if include_metrics and experiment.metrics:
            # NOTE: if duplicate metric names exist, last value wins.
            results["metrics"] = {m.name: m.value for m in experiment.metrics}

        if include_code and experiment.artifacts:
            results["artifacts"] = [
                {
                    "name": a.name,
                    "type": a.artifact_type,
                    "content": a.content,
                    "file_path": a.file_path,
                }
                for a in experiment.artifacts
                if a.content
            ]

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
            output += f"Created: {results['created_at']}\n"
            if include_metrics:
                output += "\nMetrics:\n"
                for k, v in results.get("metrics", {}).items():
                    output += f"  {k}: {v}\n"
            if include_code and results.get("artifacts"):
                output += "\nArtifacts:\n"
                for a in results["artifacts"]:
                    output += f"  [{a['type']}] {a['name']}\n"
                    if a.get("content"):
                        output += f"{a['content']}\n"

        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output)
            typer.echo(f"Results exported to {output_file}")
        else:
            typer.echo(output)
    finally:
        db.close()


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
    if not DEFAULT_DB_PATH.exists():
        typer.echo(f"Error: No experiment database found at {DEFAULT_DB_PATH}")
        typer.echo("Run an evolution cycle first to generate data.")
        raise typer.Exit(1)

    try:
        db = ExperimentDatabase(DEFAULT_DB_PATH)
    except Exception as e:
        typer.echo(f"Error reading experiment database: {e}")
        raise typer.Exit(1) from None

    try:
        try:
            # NOTE: "variants" in the CLI map to experiments in the database.
            # There is no separate Variant model; get_experiment is the correct lookup.
            experiment = db.get_experiment(variant_id)
        except Exception as e:
            typer.echo(f"Error querying experiment database: {e}")
            raise typer.Exit(1) from None

        if experiment is None:
            typer.echo(f"Error: No experiment/variant found with ID '{variant_id}'")
            raise typer.Exit(1)

        output_dir = output_dir / f"variant_{variant_id}"
        output_dir.mkdir(parents=True, exist_ok=True)

        exported_files = 0
        written_names: set[str] = set()
        if experiment.artifacts:
            for artifact in experiment.artifacts:
                # Skip dependency artifacts when the flag is off
                if not include_dependencies and artifact.artifact_type in DEPENDENCY_ARTIFACT_TYPES:
                    continue
                if artifact.content:
                    # Sanitize: use only the filename component to prevent path traversal
                    safe_name = Path(artifact.file_path or artifact.name).name
                    # Deduplicate: avoid silent overwrites when multiple artifacts
                    # collapse to the same basename
                    if safe_name in written_names:
                        stem = Path(safe_name).stem
                        suffix = Path(safe_name).suffix
                        counter = 2
                        while f"{stem}_{counter}{suffix}" in written_names:
                            counter += 1
                        safe_name = f"{stem}_{counter}{suffix}"
                    written_names.add(safe_name)
                    file_path = output_dir / safe_name
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(artifact.content)
                    exported_files += 1

        # Write experiment metadata
        metadata = {
            "id": experiment.id,
            "name": experiment.name,
            "status": experiment.status.value,
            "best_fitness": experiment.result.best_fitness if experiment.result else None,
            "generations_completed": experiment.result.generations_completed
            if experiment.result
            else 0,
        }
        (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

        # include_dependencies filtering is handled in the artifact loop above.

        typer.echo(
            f"Variant {variant_id} exported to {output_dir} ({exported_files} artifact files)"
        )
    finally:
        db.close()


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

    if not DEFAULT_DB_PATH.exists():
        typer.echo(f"Error: No experiment database found at {DEFAULT_DB_PATH}")
        typer.echo("Run an evolution cycle first to generate data.")
        raise typer.Exit(1)

    try:
        db = ExperimentDatabase(DEFAULT_DB_PATH)
    except Exception as e:
        typer.echo(f"Error reading experiment database: {e}")
        raise typer.Exit(1) from None

    try:
        try:
            experiments = db.list_experiments()
        except Exception as e:
            typer.echo(f"Error querying experiment database: {e}")
            raise typer.Exit(1) from None

        if not experiments:
            typer.echo("No experiments found in the database.")
            raise typer.Exit(1)

        output_dir.mkdir(parents=True, exist_ok=True)
        results_dir = output_dir / "results"
        results_dir.mkdir(exist_ok=True)

        # Build export records from real experiments
        results = []
        for exp in experiments:
            record: dict[str, Any] = {
                "run_id": exp.id,
                "name": exp.name,
                "status": exp.status.value,
                "created_at": exp.created_at.isoformat(),
            }
            if include_metrics and exp.result:
                record["fitness"] = exp.result.best_fitness
                record["generation"] = exp.result.generations_completed
                record["execution_time"] = exp.result.execution_time
            if include_code and exp.artifacts:
                record["artifacts"] = [a.name for a in exp.artifacts]
            results.append(record)

        if format == "json":
            with open(results_dir / "results.json", "w") as f:
                json.dump({"results": results, "count": len(results)}, f, indent=2)
        elif format == "yaml":
            import yaml

            with open(results_dir / "results.yaml", "w") as f:
                yaml.dump({"results": results, "count": len(results)}, f, default_flow_style=False)
        elif format == "csv":
            import csv

            with open(results_dir / "results.csv", "w", newline="") as f:
                if results:
                    # Compute fieldnames as union across all records to handle optional keys
                    all_keys: set[str] = set()
                    for r in results:
                        all_keys.update(r.keys())
                    fieldnames = sorted(all_keys)
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(results)

        typer.echo(f"Exported {len(results)} experiments to {output_dir}")
    finally:
        db.close()


if __name__ == "__main__":
    app()
