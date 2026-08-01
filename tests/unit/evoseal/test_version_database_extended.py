"""Extended unit tests for VersionDatabase.

Covers experiment tracking, get_best_variants, statistics, export/import,
and edge cases not covered by the original test_version_database.py.
"""

from __future__ import annotations

import json

import pytest

from evoseal.core.version_database import VersionDatabase

pytestmark = pytest.mark.unit

# --- Experiment tracking ---


def test_add_variant_with_experiment_id():
    db = VersionDatabase()
    db.add_variant("v1", "code", {}, 0.8, experiment_id="exp1")
    db.add_variant("v2", "code2", {}, 0.9, experiment_id="exp1")
    db.add_variant("v3", "code3", {}, 0.7, experiment_id="exp2")

    assert db.get_experiment_variants("exp1") == ["v1", "v2"]
    assert db.get_experiment_variants("exp2") == ["v3"]
    assert db.get_experiment_variants("nonexistent") == []


def test_get_variant_experiment():
    db = VersionDatabase()
    db.add_variant("v1", "code", {}, 0.8, experiment_id="exp1")
    assert db.get_variant_experiment("v1") == "exp1"
    assert db.get_variant_experiment("nonexistent") is None


def test_add_variant_without_experiment_id():
    db = VersionDatabase()
    db.add_variant("v1", "code", {}, 0.8)
    assert db.get_variant_experiment("v1") is None
    assert db.experiment_variants == {}


# --- get_variant_metadata ---


def test_get_variant_metadata():
    db = VersionDatabase()
    db.add_variant("v1", "code", {}, 0.8, metadata={"author": "test"})
    assert db.get_variant_metadata("v1") == {"author": "test"}


def test_get_variant_metadata_nonexistent():
    db = VersionDatabase()
    assert db.get_variant_metadata("missing") is None


def test_get_variant_metadata_no_metadata_set():
    db = VersionDatabase()
    db.add_variant("v1", "code", {}, 0.8)
    assert db.get_variant_metadata("v1") == {}


# --- get_best_variants ---


def test_get_best_variants_all():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.5)
    db.add_variant("v2", "B", {}, 0.9)
    db.add_variant("v3", "C", {}, 0.7)
    best = db.get_best_variants(limit=2)
    assert len(best) == 2
    assert best[0]["eval_score"] == 0.9
    assert best[1]["eval_score"] == 0.7


def test_get_best_variants_filtered_by_experiment():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.5, experiment_id="exp1")
    db.add_variant("v2", "B", {}, 0.9, experiment_id="exp2")
    db.add_variant("v3", "C", {}, 0.7, experiment_id="exp1")
    best = db.get_best_variants(experiment_id="exp1", limit=10)
    assert len(best) == 2
    assert best[0]["eval_score"] == 0.7
    assert best[1]["eval_score"] == 0.5


def test_get_best_variants_empty_db():
    db = VersionDatabase()
    assert db.get_best_variants() == []


def test_get_best_variants_limit_larger_than_db():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.5)
    best = db.get_best_variants(limit=100)
    assert len(best) == 1


# --- get_variant_statistics ---


def test_get_variant_statistics_basic():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.6)
    db.add_variant("v2", "B", {}, 0.9)
    db.add_variant("v3", "C", {}, 0.3)
    stats = db.get_variant_statistics()
    assert stats["total_variants"] == 3
    assert stats["best_score"] == 0.9
    assert stats["worst_score"] == 0.3
    assert abs(stats["average_score"] - 0.6) < 1e-6
    assert isinstance(stats["score_distribution"], dict)


def test_get_variant_statistics_empty():
    db = VersionDatabase()
    stats = db.get_variant_statistics()
    assert stats["total_variants"] == 0
    assert stats["best_score"] is None
    assert stats["average_score"] is None


def test_get_variant_statistics_by_experiment():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.5, experiment_id="exp1")
    db.add_variant("v2", "B", {}, 0.9, experiment_id="exp2")
    stats = db.get_variant_statistics(experiment_id="exp1")
    assert stats["total_variants"] == 1
    assert stats["best_score"] == 0.5


def test_get_variant_statistics_same_scores():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.5)
    db.add_variant("v2", "B", {}, 0.5)
    stats = db.get_variant_statistics()
    assert stats["best_score"] == 0.5
    assert stats["worst_score"] == 0.5
    # Distribution should handle min == max
    dist = stats["score_distribution"]
    assert len(dist) == 1


# --- export / import ---


def test_export_variants_returns_json_string():
    db = VersionDatabase()
    db.add_variant("v1", "code", {"passed": True}, 0.8)
    json_str = db.export_variants()
    data = json.loads(json_str)
    assert "variants" in data
    assert "v1" in data["variants"]
    assert data["variants"]["v1"]["source"] == "code"


def test_export_variants_to_file(tmp_path):
    db = VersionDatabase()
    db.add_variant("v1", "code", {}, 0.8)
    fpath = tmp_path / "export.json"
    result = db.export_variants(file_path=fpath)
    assert result is None
    assert fpath.exists()
    data = json.loads(fpath.read_text())
    assert "v1" in data["variants"]


def test_export_variants_filtered_by_experiment():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.5, experiment_id="exp1")
    db.add_variant("v2", "B", {}, 0.9, experiment_id="exp2")
    json_str = db.export_variants(experiment_id="exp1")
    data = json.loads(json_str)
    assert "v1" in data["variants"]
    assert "v2" not in data["variants"]


def test_import_variants_from_json_string():
    db = VersionDatabase()
    export_data = {
        "variants": {
            "v1": {
                "variant_id": "v1",
                "source": "code",
                "test_results": {},
                "eval_score": 0.8,
                "parent_ids": [],
                "metadata": {},
                "experiment_id": None,
            }
        },
        "lineage": {"v1": []},
    }
    count = db.import_variants(json.dumps(export_data))
    assert count == 1
    assert db.get_variant("v1") is not None
    assert db.get_variant("v1")["source"] == "code"


def test_import_variants_from_file(tmp_path):
    db = VersionDatabase()
    export_data = {
        "variants": {
            "v1": {
                "variant_id": "v1",
                "source": "code",
                "test_results": {},
                "eval_score": 0.8,
                "parent_ids": [],
                "metadata": {},
                "experiment_id": None,
            }
        },
        "lineage": {},
    }
    fpath = tmp_path / "import.json"
    fpath.write_text(json.dumps(export_data))
    count = db.import_variants(str(fpath))
    assert count == 1


def test_import_variants_skips_duplicates():
    db = VersionDatabase()
    db.add_variant("v1", "original", {}, 0.5)
    export_data = {
        "variants": {
            "v1": {
                "variant_id": "v1",
                "source": "imported",
                "test_results": {},
                "eval_score": 0.9,
                "parent_ids": [],
                "metadata": {},
                "experiment_id": None,
            }
        },
        "lineage": {},
    }
    count = db.import_variants(json.dumps(export_data))
    assert count == 0
    assert db.get_variant("v1")["source"] == "original"


def test_import_variants_with_experiment_tracking():
    db = VersionDatabase()
    export_data = {
        "variants": {
            "v1": {
                "variant_id": "v1",
                "source": "code",
                "test_results": {},
                "eval_score": 0.8,
                "parent_ids": [],
                "metadata": {},
                "experiment_id": "exp1",
            }
        },
        "lineage": {},
    }
    db.import_variants(json.dumps(export_data))
    assert db.get_variant_experiment("v1") == "exp1"
    assert "v1" in db.get_experiment_variants("exp1")


def test_import_variants_preserves_lineage():
    db = VersionDatabase()
    export_data = {
        "variants": {
            "v1": {"variant_id": "v1", "source": "A", "test_results": {}, "eval_score": 0.5},
            "v2": {"variant_id": "v2", "source": "B", "test_results": {}, "eval_score": 0.8},
        },
        "lineage": {"v2": ["v1"]},
    }
    db.import_variants(json.dumps(export_data))
    assert db.get_lineage("v2") == ["v1"]


# --- Edge cases ---


def test_query_variants_no_match():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.5)
    assert db.query_variants({"source": "Z"}) == []


def test_query_variants_empty_db():
    db = VersionDatabase()
    assert db.query_variants({}) == []


def test_get_lineage_nonexistent():
    db = VersionDatabase()
    assert db.get_lineage("missing") == []


def test_get_variant_nonexistent():
    db = VersionDatabase()
    assert db.get_variant("missing") is None
