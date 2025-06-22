import os
import shutil
import tempfile

import pytest

from evoseal.models.code_archive import CodeArchive, create_code_archive
from evoseal.models.evaluation import EvaluationResult, TestCaseResult
from evoseal.integration.dgm.data_adapter import DGMDataAdapter


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def test_save_and_load_code_archive(temp_dir):
    adapter = DGMDataAdapter(temp_dir)
    archive = create_code_archive(
        content="print('hello')",
        language="python",
        title="Test Agent",
        author_id="user1",
        version="1.0.0",
        tags=["test"],
        description="desc",
        metadata={"foo": "bar"},
    )
    adapter.save_code_archive(archive)
    loaded = adapter.load_code_archive(archive.id)
    assert loaded is not None
    assert loaded.content == "print('hello')"
    assert loaded.title == "Test Agent"
    assert loaded.metadata["foo"] == "bar"


def test_save_and_load_evaluation_result(temp_dir):
    adapter = DGMDataAdapter(temp_dir)
    test_case = TestCaseResult(
        name="case1",
        passed=True,
        input_data="x",
        expected_output="y",
        actual_output="y",
        error_message=None,
    )
    accuracy_score = 0.9
    result = EvaluationResult(
        code_archive_id="archive123",
        metrics={"accuracy": accuracy_score},
        test_case_results=[test_case],
    )
    adapter.save_evaluation_result(result)
    loaded = adapter.load_evaluation_result(result.id)
    assert loaded is not None
    assert loaded.metrics["accuracy"] == accuracy_score
    assert loaded.test_case_results[0].name == "case1"


def test_run_output_to_code_archive(temp_dir):
    adapter = DGMDataAdapter(temp_dir)
    metadata = {
        "language": "python",
        "title": "Agent",
        "author_id": "user2",
        "version": "1.2.3",
        "tags": ["foo"],
        "description": "desc",
    }
    archive = adapter.run_output_to_code_archive("run123", "code...", metadata)
    assert isinstance(archive, CodeArchive)
    assert archive.language == "python"
    assert archive.title == "Agent"
    assert archive.author_id == "user2"
    assert archive.version == "1.2.3"
    assert archive.tags == ["foo"]
    assert archive.description == "desc"


def test_run_output_to_evaluation_result(temp_dir):
    adapter = DGMDataAdapter(temp_dir)
    metrics = {"score": 1.0}
    test_cases = [
        {
            "name": "t1",
            "passed": True,
            "input_data": "a",
            "expected_output": "b",
            "actual_output": "b",
            "error_message": None,
        }
    ]
    result = adapter.run_output_to_evaluation_result(
        "run999", metrics, test_cases, "archive999"
    )
    assert isinstance(result, EvaluationResult)
    assert result.code_archive_id == "archive999"
    assert result.metrics["score"] == 1.0
    assert result.test_case_results[0].name == "t1"
