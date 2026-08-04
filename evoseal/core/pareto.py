"""Pareto front computation and multi-objective visualization.

Provides tools for computing Pareto-optimal fronts from experiment data
and generating SVG scatter-plot visualizations showing trade-offs between
competing objectives (e.g., correctness vs. efficiency, fitness vs. cost).
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParetoPoint:
    """A single point in objective space with metadata."""

    values: tuple[float, ...]
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    dominated: bool = False


@dataclass
class ParetoResult:
    """Result of a Pareto front computation."""

    points: list[ParetoPoint]
    front_indices: list[int]
    objective_names: list[str]
    minimize: list[bool]

    @property
    def front(self) -> list[ParetoPoint]:
        """Return only the Pareto-optimal points."""
        return [self.points[i] for i in self.front_indices]

    @property
    def dominated_points(self) -> list[ParetoPoint]:
        """Return only the dominated points."""
        front_set = set(self.front_indices)
        return [p for i, p in enumerate(self.points) if i not in front_set]


def dominates(
    a: tuple[float, ...],
    b: tuple[float, ...],
    minimize: list[bool] | None = None,
) -> bool:
    """Check whether point *a* Pareto-dominates point *b*.

    Args:
        a: First point (tuple of objective values).
        b: Second point (tuple of objective values).
        minimize: Per-objective flag — True = minimize, False = maximize.
            Defaults to minimizing all objectives.

    Returns:
        True if *a* dominates *b* (strictly better in at least one
        objective and no worse in any).
    """
    if len(a) != len(b):
        raise ValueError(f"Point dimensions differ: {len(a)} vs {len(b)}")

    if minimize is None:
        minimize = [True] * len(a)

    if len(minimize) != len(a):
        raise ValueError(f"minimize length ({len(minimize)}) must match point dimension ({len(a)})")

    strictly_better = False
    for va, vb, do_min in zip(a, b, minimize):
        if do_min:
            if va > vb:
                return False
            if va < vb:
                strictly_better = True
        else:
            if va < vb:
                return False
            if va > vb:
                strictly_better = True

    return strictly_better


def compute_pareto_front(
    points: list[tuple[float, ...]],
    minimize: list[bool] | None = None,
    labels: list[str] | None = None,
    metadata: list[dict[str, Any]] | None = None,
) -> ParetoResult:
    """Compute the Pareto front for a set of multi-objective points.

    Args:
        points: List of tuples, each containing objective values.
        minimize: Per-objective direction. True = minimize, False = maximize.
            Defaults to minimizing all objectives.
        labels: Optional label for each point.
        metadata: Optional metadata dict for each point.

    Returns:
        ParetoResult with front membership and dominated status.

    Raises:
        ValueError: If points list is empty or dimensions are inconsistent.
    """
    if not points:
        raise ValueError("Cannot compute Pareto front of an empty point set")

    n_dims = len(points[0])
    if any(len(p) != n_dims for p in points):
        raise ValueError("All points must have the same number of dimensions")

    if minimize is None:
        minimize = [True] * n_dims

    if len(minimize) != n_dims:
        raise ValueError(f"minimize length ({len(minimize)}) must match point dimension ({n_dims})")

    n = len(points)
    is_dominated = [False] * n

    # O(n^2 * d) pairwise comparison — fine for typical experiment counts
    for i in range(n):
        if is_dominated[i]:
            continue
        for j in range(i + 1, n):
            if is_dominated[j]:
                continue
            if dominates(points[i], points[j], minimize):
                is_dominated[j] = True
            elif dominates(points[j], points[i], minimize):
                is_dominated[i] = True
                break

    pareto_points = []
    front_indices = []
    for i, (pt, dom) in enumerate(zip(points, is_dominated)):
        pp = ParetoPoint(
            values=pt,
            label=labels[i] if labels else "",
            metadata=metadata[i] if metadata else {},
            dominated=dom,
        )
        pareto_points.append(pp)
        if not dom:
            front_indices.append(i)

    return ParetoResult(
        points=pareto_points,
        front_indices=front_indices,
        objective_names=[f"objective_{i}" for i in range(n_dims)],
        minimize=minimize,
    )


def compute_pareto_front_from_experiments(
    experiments: list[dict[str, Any]],
    objective_names: list[str],
    minimize: list[bool] | None = None,
) -> ParetoResult:
    """Compute Pareto front from experiment dicts.

    Each experiment dict should have a "metrics" key mapping to a dict
    of metric name → float value. Experiments missing any required
    objective metric are silently skipped.

    Args:
        experiments: List of experiment dicts with "metrics" sub-dicts.
        objective_names: Names of the metrics to use as objectives.
        minimize: Per-objective direction. Defaults to minimizing all.

    Returns:
        ParetoResult for the valid experiments.
    """
    points = []
    labels = []
    metadata = []
    for exp in experiments:
        metrics = exp.get("metrics", {})
        if not all(name in metrics for name in objective_names):
            continue
        pt = tuple(float(metrics[name]) for name in objective_names)
        points.append(pt)
        labels.append(exp.get("name", exp.get("id", "")))
        metadata.append({"experiment_id": exp.get("id", ""), "metrics": metrics})

    if not points:
        raise ValueError(f"No experiments have all required metrics: {objective_names}")

    return compute_pareto_front(points, minimize=minimize, labels=labels, metadata=metadata)


def hv_ratio(result: ParetoResult) -> float:
    """Compute a simple hypervolume ratio for 2-D fronts.

    Returns the ratio of the dominated area to the bounding-box area.
    Only meaningful for 2 objectives. Returns 0.0 for fewer than 2
    front points or degenerate bounding boxes.
    """
    if len(result.front) < 2 or len(result.objective_names) != 2:
        return 0.0

    front_vals = sorted(
        [p.values for p in result.front],
        key=lambda v: v[0],
    )

    # Bounding box
    all_vals = [p.values for p in result.points]
    x_min = min(v[0] for v in all_vals)
    x_max = max(v[0] for v in all_vals)
    y_min = min(v[1] for v in all_vals)
    y_max = max(v[1] for v in all_vals)

    x_range = x_max - x_min
    y_range = y_max - y_min
    if x_range == 0 or y_range == 0:
        return 0.0

    # Staircase area under the front (assumes minimize both)
    area = 0.0
    prev_x, prev_y = front_vals[0]
    for x, y in front_vals[1:]:
        area += (x - prev_x) * (y_max - prev_y)
        prev_x, prev_y = x, y
    # Last segment
    area += (x_max - prev_x) * (y_max - prev_y)

    return area / (x_range * y_range)


# ---------------------------------------------------------------------------
# SVG visualization
# ---------------------------------------------------------------------------

# Default color palette for generations
_GEN_COLORS = [
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ac",
]


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def generate_pareto_svg(
    result: ParetoResult,
    width: int = 700,
    height: int = 500,
    title: str = "Pareto Front",
    x_label: str | None = None,
    y_label: str | None = None,
    generation_key: str = "generation",
) -> str:
    """Generate an SVG scatter plot of the Pareto front.

    Args:
        result: Computed Pareto result (must be 2-D).
        width: SVG width in pixels.
        height: SVG height in pixels.
        title: Chart title.
        x_label: Override for x-axis label (defaults to objective name).
        y_label: Override for y-axis label (defaults to objective name).
        generation_key: Metadata key used to color points by generation.

    Returns:
        SVG markup as a string.

    Raises:
        ValueError: If the result is not 2-dimensional.
    """
    if len(result.objective_names) != 2:
        raise ValueError(
            f"SVG visualization requires 2 objectives, got {len(result.objective_names)}"
        )

    mt, mr, mb, ml = 60, 30, 60, 70  # margins
    plot_w = width - ml - mr
    plot_h = height - mt - mb

    all_vals = [p.values for p in result.points]
    x_min = min(v[0] for v in all_vals)
    x_max = max(v[0] for v in all_vals)
    y_min = min(v[1] for v in all_vals)
    y_max = max(v[1] for v in all_vals)

    # Add 5% padding
    x_pad = (x_max - x_min) * 0.05 or 1.0
    y_pad = (y_max - y_min) * 0.05 or 1.0
    x_min -= x_pad
    x_max += x_pad
    y_min -= y_pad
    y_max += y_pad

    def scale_x(v: float) -> float:
        return ml + (v - x_min) / (x_max - x_min) * plot_w

    def scale_y(v: float) -> float:
        return mt + plot_h - (v - y_min) / (y_max - y_min) * plot_h

    # Gather unique generations for coloring
    generations: dict[int, str] = {}
    for p in result.points:
        gen = p.metadata.get(generation_key)
        if gen is not None and gen not in generations:
            generations[gen] = _GEN_COLORS[len(generations) % len(_GEN_COLORS)]

    def point_color(p: ParetoPoint) -> str:
        gen = p.metadata.get(generation_key)
        if gen is not None and gen in generations:
            return generations[gen]
        return "#888888"

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="sans-serif">'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="white"/>')

    # Title
    parts.append(
        f'<text x="{width // 2}" y="30" text-anchor="middle" font-size="16" '
        f'font-weight="bold">{html.escape(title)}</text>'
    )

    # Axes
    lx = x_label or result.objective_names[0]
    ly = y_label or result.objective_names[1]
    ax = ml + plot_w // 2
    ay = mt + plot_h // 2
    parts.append(
        f'<text x="{ax}" y="{height - 10}" text-anchor="middle" '
        f'font-size="13">{html.escape(lx)}</text>'
    )
    parts.append(
        f'<text x="18" y="{ay}" text-anchor="middle" '
        f'font-size="13" transform="rotate(-90,18,{ay})">'
        f"{html.escape(ly)}</text>"
    )

    # Grid lines (5 ticks each axis)
    for i in range(6):
        frac = i / 5
        gx = ml + frac * plot_w
        gy = mt + frac * plot_h
        parts.append(
            f'<line x1="{gx}" y1="{mt}" x2="{gx}" y2="{mt + plot_h}" '
            f'stroke="#e0e0e0" stroke-width="1"/>'
        )
        xv = x_min + frac * (x_max - x_min)
        parts.append(
            f'<text x="{gx}" y="{mt + plot_h + 18}" text-anchor="middle" '
            f'font-size="11" fill="#666">{xv:.3g}</text>'
        )
        parts.append(
            f'<line x1="{ml}" y1="{gy}" x2="{ml + plot_w}" y2="{gy}" '
            f'stroke="#e0e0e0" stroke-width="1"/>'
        )
        yv = y_max - frac * (y_max - y_min)
        parts.append(
            f'<text x="{ml - 10}" y="{gy + 4}" text-anchor="end" '
            f'font-size="11" fill="#666">{yv:.3g}</text>'
        )

    # Plot area border
    parts.append(
        f'<rect x="{ml}" y="{mt}" width="{plot_w}" height="{plot_h}" '
        f'fill="none" stroke="#ccc" stroke-width="1"/>'
    )

    # Connect front points with a polyline (sorted by x)
    front_sorted = sorted(result.front, key=lambda p: p.values[0])
    if len(front_sorted) >= 2:
        polyline_pts = " ".join(
            f"{scale_x(p.values[0]):.1f},{scale_y(p.values[1]):.1f}" for p in front_sorted
        )
        parts.append(
            f'<polyline points="{polyline_pts}" fill="none" stroke="#e15759" '
            f'stroke-width="2" stroke-dasharray="6,3" opacity="0.7"/>'
        )

    # Dominated points (smaller, semi-transparent)
    for p in result.dominated_points:
        cx = scale_x(p.values[0])
        cy = scale_y(p.values[1])
        color = point_color(p)
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{color}" '
            f'opacity="0.4" stroke="none"/>'
        )

    # Front points (larger, bright)
    for p in result.front:
        cx = scale_x(p.values[0])
        cy = scale_y(p.values[1])
        color = point_color(p)
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{color}" '
            f'opacity="0.9" stroke="white" stroke-width="1.5"/>'
        )
        if p.label:
            safe = html.escape(p.label[:20])
            parts.append(
                f'<text x="{cx + 10:.1f}" y="{cy - 8:.1f}" font-size="10" fill="#333">{safe}</text>'
            )

    # Legend for generations
    if generations:
        legend_x = width - mr - 140
        legend_y = mt + 10
        legend_h = len(generations) * 20 + 10
        parts.append(
            f'<rect x="{legend_x - 8}" y="{legend_y - 5}" width="135" '
            f'height="{legend_h}" fill="white" stroke="#ddd" rx="4"/>'
        )
        for idx, (gen, color) in enumerate(sorted(generations.items())):
            yy = legend_y + idx * 20
            parts.append(f'<circle cx="{legend_x}" cy="{yy}" r="5" fill="{color}"/>')
            parts.append(f'<text x="{legend_x + 12}" y="{yy + 4}" font-size="11">Gen {gen}</text>')

    # Summary stats
    hv = hv_ratio(result)
    parts.append(
        f'<text x="{ml}" y="{height - 28}" font-size="11" fill="#666">'
        f"Front: {len(result.front)} / {len(result.points)} points | "
        f"HV ratio: {hv:.3f}</text>"
    )

    parts.append("</svg>")
    return "\n".join(parts)
