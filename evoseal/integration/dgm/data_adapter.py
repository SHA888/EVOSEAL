import json
import os
from typing import Any, Optional

from evoseal.models.code_archive import CodeArchive, create_code_archive
from evoseal.models.evaluation import EvaluationResult, TestCaseResult


class DGMDataAdapter:
    """
    Adapter to bridge DGM run outputs (code, metadata, metrics) into structured EVOSEAL models.
    Provides methods to convert, save, and load CodeArchive and EvaluationResult objects from disk.
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir  # Root directory for agent/code and results

    # ---- Code Archive ----
    def save_code_archive(self, archive: CodeArchive) -> None:
        path = os.path.join(self.base_dir, "code_archives", f"{archive.id}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(archive.to_json(indent=2))

    def load_code_archive(self, archive_id: str) -> Optional[CodeArchive]:
        path = os.path.join(self.base_dir, "code_archives", f"{archive_id}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            result = CodeArchive.model_validate_json(f.read())
            assert isinstance(result, CodeArchive)
            return result

    # ---- Evaluation Result ----
    def save_evaluation_result(self, result: EvaluationResult) -> None:
        path = os.path.join(self.base_dir, "evaluation_results", f"{result.id}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(result.to_json(indent=2))

    def load_evaluation_result(self, result_id: str) -> Optional[EvaluationResult]:
        path = os.path.join(self.base_dir, "evaluation_results", f"{result_id}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return EvaluationResult.from_json(f.read())

    # ---- Conversion Methods ----
    def run_output_to_code_archive(
        self, run_id: str, code: str, metadata: dict[str, Any]
    ) -> CodeArchive:
        """
        Convert a DGM run output (code + metadata) to a CodeArchive instance.
        """
        return create_code_archive(
            content=code,
            language=metadata.get("language", "python"),
            title=metadata.get("title", f"agent_{run_id}"),
            author_id=metadata.get("author_id", "unknown"),
            version=metadata.get("version", "1.0.0"),
            tags=metadata.get("tags", []),
            description=metadata.get("description", ""),
            metadata=metadata,
        )

    def run_output_to_evaluation_result(
        self,
        run_id: str,
        metrics: dict[str, float],
        test_cases: list[dict[str, Any]],
        code_archive_id: str,
    ) -> EvaluationResult:
        """
        Convert DGM run metrics and test cases to an EvaluationResult instance.
        """
        return EvaluationResult(
            code_archive_id=code_archive_id,
            metrics=metrics,
            test_case_results=[TestCaseResult(**tc) for tc in test_cases],
        )
