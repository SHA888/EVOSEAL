"""EVOSEAL models package."""

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

# Import other models at the top level
from .code_archive import CodeArchive, CodeLanguage, CodeVisibility
from .evaluation import EvaluationResult, TestCaseResult
from .system_config import SystemConfig


class Program(BaseModel):
    """Represents a program in the EVOSEAL system.

    Attributes:
        id: Unique identifier for the program
        code: The program's source code
        language: Programming language of the code
        metadata: Additional metadata about the program
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    code: str
    language: str = "python"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __str__(self) -> str:
        return f"Program(id={self.id}, language={self.language}, code_length={len(self.code)})"


__all__ = [
    "Program",
    "CodeArchive",
    "CodeLanguage",
    "CodeVisibility",
    "EvaluationResult",
    "TestCaseResult",
    "SystemConfig",
]
