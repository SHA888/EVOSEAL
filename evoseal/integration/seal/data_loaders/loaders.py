"""
Data loaders for various file formats.

This module provides loaders for different file formats (JSON, YAML, CSV)
with support for Pydantic model validation.
"""

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, cast

import yaml
from pydantic import BaseModel, ValidationError

from .types import DataFormat, ModelType

T = TypeVar("T", bound=BaseModel)


class DataLoader(ABC, Generic[T]):
    """Abstract base class for data loaders."""

    @classmethod
    def from_file(cls, file_path: Union[str, Path], model: Type[T], **kwargs: Any) -> List[T]:
        """Load data from a file.

        Args:
            file_path: Path to the file to load
            model: Pydantic model to validate the data against
            **kwargs: Additional arguments to pass to the loader

        Returns:
            List of validated model instances
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        format = file_path.suffix.lstrip(".").lower()
        try:
            format_enum = DataFormat(format)
        except ValueError as e:
            raise ValueError(f"Unsupported file format: {format}") from e

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return cls.from_string(content, format_enum, model, **kwargs)

    @classmethod
    @abstractmethod
    def from_string(
        cls, content: str, format: DataFormat, model: Type[T], **kwargs: Any
    ) -> List[T]:
        """Load data from a string.

        Args:
            content: String content to parse
            format: Format of the content
            model: Pydantic model to validate the data against
            **kwargs: Additional arguments to pass to the parser

        Returns:
            List of validated model instances
        """
        pass


class JSONLoader(DataLoader[T]):
    """Loader for JSON data."""

    @classmethod
    def from_string(
        cls, content: str, format: DataFormat, model: Type[T], **kwargs: Any
    ) -> List[T]:
        if format != DataFormat.JSON:
            raise ValueError(f"JSONLoader only supports JSON format, got {format}")

        try:
            data = json.loads(content)
            if data is None:
                return []
            if isinstance(data, dict):
                data = [data]
            elif not isinstance(data, list):
                data = [{"data": data}]
            return [model.model_validate(item) for item in data]
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        except ValidationError as e:
            raise ValueError(f"Validation error: {e}")


class YAMLLoader(DataLoader[T]):
    """Loader for YAML data."""

    @classmethod
    def from_string(
        cls, content: str, format: DataFormat, model: Type[T], **kwargs: Any
    ) -> List[T]:
        if format not in (DataFormat.YAML, DataFormat.YML):
            raise ValueError(f"YAMLLoader only supports YAML format, got {format}")

        try:
            data = yaml.safe_load(content)
            if data is None:
                return []
            if isinstance(data, dict):
                data = [data]
            elif not isinstance(data, list):
                data = [{"data": data}]
            return [model.model_validate(item) for item in data]
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")
        except ValidationError as e:
            raise ValueError(f"Validation error: {e}")


class CSVLoader(DataLoader[T]):
    """Loader for CSV data."""

    @classmethod
    def from_string(
        cls, content: str, format: DataFormat, model: Type[T], **kwargs: Any
    ) -> List[T]:
        if format != DataFormat.CSV:
            raise ValueError(f"CSVLoader only supports CSV format, got {format}")

        try:
            # Read CSV content and strip whitespace from field names and values
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            if not lines:
                return []

            # Create CSV reader with proper handling of field names
            reader = csv.DictReader(lines, skipinitialspace=True)

            # Convert CSV data to model instances
            results = []
            for row in reader:
                # Clean up row data (convert string 'true'/'false' to boolean)
                cleaned_row = {}
                for k, v in row.items():
                    if v.lower() == "true":
                        cleaned_row[k] = True
                    elif v.lower() == "false":
                        cleaned_row[k] = False
                    elif v.isdigit():
                        cleaned_row[k] = int(v)
                    else:
                        cleaned_row[k] = v.strip()

                # Convert to model
                results.append(model.model_validate(cleaned_row))

            return results

        except csv.Error as e:
            raise ValueError(f"CSV parsing error: {e}")
        except ValidationError as e:
            raise ValueError(f"Validation error: {e}")
        except Exception as e:
            raise ValueError(f"Error processing CSV data: {e}")


# Factory function for getting the appropriate loader
def get_loader(format: Union[str, DataFormat]) -> Type[DataLoader]:
    """Get the appropriate loader for the given format.

    Args:
        format: Format to get loader for

    Returns:
        DataLoader subclass for the specified format
    """
    if isinstance(format, str):
        try:
            format = DataFormat(format.lower())
        except ValueError:
            raise ValueError(f"Unsupported format: {format}")

    loaders = {
        DataFormat.JSON: JSONLoader,
        DataFormat.YAML: YAMLLoader,
        DataFormat.YML: YAMLLoader,
        DataFormat.CSV: CSVLoader,
    }

    return loaders.get(format, JSONLoader)  # Default to JSON if format not found


def load_data(
    source: Union[str, Path],
    model: Type[T],
    format: Optional[Union[str, DataFormat]] = None,
    **kwargs: Any,
) -> List[T]:
    """Load data from a source with automatic format detection.

    Args:
        source: Source to load from (file path or string content)
        model: Pydantic model to validate the data against
        format: Optional format hint (auto-detected from file extension if not provided)
        **kwargs: Additional arguments to pass to the loader

    Returns:
        List of validated model instances
    """
    # If source is a file path
    if isinstance(source, (str, Path)) and Path(source).exists():
        file_path = Path(source)
        if format is None:
            format = file_path.suffix.lstrip(".").lower()
        return get_loader(format).from_file(file_path, model, **kwargs)

    # If source is a string and format is specified
    if format is not None and isinstance(source, str):
        return get_loader(format).from_string(source, format, model, **kwargs)

    raise ValueError(
        "Could not determine how to load the data. "
        "Either provide a valid file path or specify the format."
    )
