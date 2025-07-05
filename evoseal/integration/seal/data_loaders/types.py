"""
Shared types and enums for the data loaders module.
"""

from enum import Enum, auto
from typing import Type, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel


class DataFormat(str, Enum):
    """Supported data formats for loading and saving."""

    JSON = "json"
    YAML = "yaml"
    YML = "yml"  # Alias for YAML
    CSV = "csv"

    @classmethod
    def from_extension(cls, ext: str) -> "DataFormat":
        """Get the format from a file extension."""
        ext = ext.lower().lstrip(".")
        if ext == "yml":
            ext = "yaml"
        try:
            return cls(ext)
        except ValueError as e:
            raise ValueError(f"Unsupported file extension: {ext}") from e


# Type variable for generic model type
ModelType = TypeVar("ModelType", bound=BaseModel)

# Type alias for supported model types
SupportedModel = Union[BaseModel, dict, list, str, int, float, bool, None]
