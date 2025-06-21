"""
Unit tests for the VersionDatabase class in evoseal.
Covers add, get, query, lineage, and history functionality.
"""

import pytest

from evoseal.version_database import VersionDatabase

MAGIC_EVAL_SCORE = 0.95
MAGIC_QUERY_RESULT_LEN = 2


def test_add_and_get_variant():
    db = VersionDatabase()
    db.add_variant(
        variant_id="v1",
        source="print('hello')",
        test_results={"passed": True},
        eval_score=MAGIC_EVAL_SCORE,
        parent_ids=["root"],
        metadata={"note": "seed"},
    )
    v = db.get_variant("v1")
    assert v["variant_id"] == "v1"
    assert v["source"] == "print('hello')"
    assert v["test_results"]["passed"]
    assert v["eval_score"] == MAGIC_EVAL_SCORE
    assert v["parent_ids"] == ["root"]
    assert v["metadata"]["note"] == "seed"


def test_query_variants():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.8)
    db.add_variant("v2", "B", {}, 0.9)
    db.add_variant("v3", "A", {}, 0.95)
    results = db.query_variants({"source": "A"})
    assert len(results) == MAGIC_QUERY_RESULT_LEN
    results = db.query_variants({"eval_score": 0.9})
    assert len(results) == 1
    assert results[0]["variant_id"] == "v2"


def test_lineage_and_history():
    db = VersionDatabase()
    db.add_variant("v1", "A", {}, 0.8, parent_ids=["root"])
    db.add_variant("v2", "B", {}, 0.9, parent_ids=["v1"])
    db.add_variant("v3", "C", {}, 0.7, parent_ids=["v2"])
    assert db.get_lineage("v2") == ["v1"]
    assert db.get_lineage("v3") == ["v2"]
    assert db.get_lineage("notfound") == []
    assert db.get_evolution_history() == ["v1", "v2", "v3"]
