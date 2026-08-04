"""Tests for Pareto front computation and SVG visualization."""

from __future__ import annotations

import pytest

from evoseal.core.pareto import (
    ParetoPoint,
    ParetoResult,
    compute_pareto_front,
    compute_pareto_front_from_experiments,
    dominates,
    generate_pareto_svg,
    hv_ratio,
)


class TestDominates:
    """Tests for the dominates() helper."""

    def test_dominates_min_all(self):
        assert dominates((1, 2), (3, 4)) is True
        assert dominates((3, 4), (1, 2)) is False

    def test_dominates_equal_not_strict(self):
        assert dominates((1, 2), (1, 2)) is False

    def test_dominates_one_better_one_equal(self):
        assert dominates((1, 2), (1, 3)) is True
        assert dominates((1, 3), (1, 2)) is False

    def test_dominates_tradeoff_no_dominance(self):
        assert dominates((1, 5), (3, 2)) is False
        assert dominates((3, 2), (1, 5)) is False

    def test_dominates_maximize(self):
        assert dominates((5, 5), (3, 3), minimize=[False, False]) is True
        assert dominates((3, 3), (5, 5), minimize=[False, False]) is False

    def test_dominates_mixed_objectives(self):
        # minimize first, maximize second
        assert dominates((1, 5), (3, 2), minimize=[True, False]) is True
        assert dominates((3, 2), (1, 5), minimize=[True, False]) is False

    def test_dominates_dimension_mismatch(self):
        with pytest.raises(ValueError, match="dimensions differ"):
            dominates((1,), (2, 3))

    def test_dominates_minimize_length_mismatch(self):
        with pytest.raises(ValueError, match="minimize length"):
            dominates((1, 2), (3, 4), minimize=[True])


class TestComputeParetoFront:
    """Tests for compute_pareto_front()."""

    def test_empty_points(self):
        with pytest.raises(ValueError, match="empty"):
            compute_pareto_front([])

    def test_single_point(self):
        result = compute_pareto_front([(1.0, 2.0)])
        assert len(result.front_indices) == 1
        assert result.front[0].values == (1.0, 2.0)

    def test_two_dominated_points(self):
        result = compute_pareto_front([(1, 2), (3, 4)])
        assert result.front_indices == [0]
        assert result.points[1].dominated is True

    def test_two_non_dominated_points(self):
        result = compute_pareto_front([(1, 5), (3, 2)])
        assert len(result.front_indices) == 2
        assert all(not p.dominated for p in result.points)

    def test_classic_pareto(self):
        points = [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)]
        result = compute_pareto_front(points)
        # All are on the front (each is best in one objective)
        assert len(result.front_indices) == 5

    def test_dominated_in_middle(self):
        points = [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1), (3, 4)]
        result = compute_pareto_front(points)
        assert 5 not in result.front_indices  # (3, 4) is dominated
        assert result.points[5].dominated is True

    def test_maximize_objectives(self):
        points = [(1, 1), (3, 3), (2, 2)]
        result = compute_pareto_front(points, minimize=[False, False])
        assert result.front_indices == [1]  # (3, 3) dominates all

    def test_three_dimensions(self):
        points = [(1, 1, 1), (2, 2, 2), (1, 2, 2), (2, 1, 2)]
        result = compute_pareto_front(points)
        # (1,1,1) dominates all others
        assert result.front_indices == [0]

    def test_labels_preserved(self):
        result = compute_pareto_front(
            [(1, 5), (3, 2)],
            labels=["A", "B"],
        )
        assert result.front[0].label == "A"
        assert result.front[1].label == "B"

    def test_metadata_preserved(self):
        meta = [{"id": "a"}, {"id": "b"}]
        result = compute_pareto_front([(1, 5), (3, 2)], metadata=meta)
        assert result.front[0].metadata == {"id": "a"}

    def test_inconsistent_dimensions(self):
        with pytest.raises(ValueError, match="same number of dimensions"):
            compute_pareto_front([(1, 2), (3,)])


class TestComputeParetoFrontFromExperiments:
    """Tests for compute_pareto_front_from_experiments()."""

    def test_basic(self):
        experiments = [
            {"id": "exp1", "metrics": {"accuracy": 0.9, "latency": 100}},
            {"id": "exp2", "metrics": {"accuracy": 0.8, "latency": 50}},
            {"id": "exp3", "metrics": {"accuracy": 0.95, "latency": 200}},
        ]
        result = compute_pareto_front_from_experiments(
            experiments, ["accuracy", "latency"], minimize=[False, True]
        )
        # No experiment dominates another — all 3 trade off differently
        assert len(result.front) == 3

    def test_missing_metrics_skipped(self):
        experiments = [
            {"id": "a", "metrics": {"x": 1, "y": 2}},
            {"id": "b", "metrics": {"x": 3}},  # missing y
            {"id": "c", "metrics": {"x": 2, "y": 1}},
        ]
        result = compute_pareto_front_from_experiments(experiments, ["x", "y"])
        assert len(result.points) == 2  # b was skipped

    def test_all_missing(self):
        experiments = [{"id": "a", "metrics": {"x": 1}}]
        with pytest.raises(ValueError, match="No experiments"):
            compute_pareto_front_from_experiments(experiments, ["x", "y"])


class TestHvRatio:
    """Tests for hv_ratio()."""

    def test_perfect_front(self):
        # Points on anti-diagonal: staircase area is 25/100 = 0.25
        points = [(0, 10), (5, 5), (10, 0)]
        result = compute_pareto_front(points)
        ratio = hv_ratio(result)
        assert ratio == pytest.approx(0.25)

    def test_single_point_front(self):
        result = compute_pareto_front([(1, 1)])
        assert hv_ratio(result) == 0.0

    def test_three_dimensions_returns_zero(self):
        result = compute_pareto_front([(1, 2, 3), (4, 5, 6)])
        assert hv_ratio(result) == 0.0


class TestGenerateSvg:
    """Tests for generate_pareto_svg()."""

    def _make_2d_result(self):
        points = [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1), (3, 4)]
        return compute_pareto_front(
            points,
            labels=["A", "B", "C", "D", "E", "F"],
            metadata=[{"generation": i} for i in range(6)],
        )

    def test_basic_svg(self):
        result = self._make_2d_result()
        svg = generate_pareto_svg(result)
        assert svg.startswith("<svg")
        assert "</svg>" in svg
        assert "Pareto Front" in svg

    def test_custom_labels(self):
        result = self._make_2d_result()
        svg = generate_pareto_svg(result, x_label="Correctness", y_label="Speed")
        assert "Correctness" in svg
        assert "Speed" in svg

    def test_custom_title(self):
        result = self._make_2d_result()
        svg = generate_pareto_svg(result, title="My Chart")
        assert "My Chart" in svg

    def test_three_dimensions_raises(self):
        result = compute_pareto_front([(1, 2, 3)])
        with pytest.raises(ValueError, match="2 objectives"):
            generate_pareto_svg(result)

    def test_contains_front_stats(self):
        result = self._make_2d_result()
        svg = generate_pareto_svg(result)
        assert "Front:" in svg
        assert "HV ratio:" in svg

    def test_contains_circles(self):
        result = self._make_2d_result()
        svg = generate_pareto_svg(result)
        assert "<circle" in svg

    def test_generation_legend(self):
        result = self._make_2d_result()
        svg = generate_pareto_svg(result)
        assert "Gen" in svg

    def test_front_line(self):
        result = self._make_2d_result()
        svg = generate_pareto_svg(result)
        assert "polyline" in svg


class TestParetoResultProperties:
    """Tests for ParetoResult convenience properties."""

    def test_front_property(self):
        result = compute_pareto_front([(1, 5), (3, 2), (2, 4)])
        front = result.front
        assert all(not p.dominated for p in front)

    def test_dominated_points_property(self):
        points = [(1, 5), (3, 2), (2, 4), (3, 5)]
        result = compute_pareto_front(points)
        dominated = result.dominated_points
        assert all(p.dominated for p in dominated)
        assert len(dominated) + len(result.front) == len(points)
