"""Checkpoint management system for EVOSEAL evolution pipeline.

This module provides comprehensive checkpoint management capabilities including
creation, restoration, listing, and metadata management for version control
and experiment tracking integration.
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..models.experiment import Experiment
from .logging_system import get_logger

logger = get_logger(__name__)


class CheckpointError(Exception):
    """Base exception for checkpoint operations."""

    pass


class CheckpointManager:
    """Manages checkpoints for the EVOSEAL evolution pipeline.

    Provides functionality to create, restore, list, and manage checkpoints
    with metadata storage and version tracking integration.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the checkpoint manager.

        Args:
            config: Configuration dictionary with checkpoint settings
        """
        self.config = config or {}
        self.checkpoint_dir = Path(self.config.get('checkpoint_directory', './checkpoints'))
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Checkpoint registry: version_id -> checkpoint_path
        self.checkpoints: Dict[str, str] = {}

        # Configuration
        self.max_checkpoints = self.config.get('max_checkpoints', 100)
        self.auto_cleanup = self.config.get('auto_cleanup', True)
        self.compression_enabled = self.config.get('compression', False)

        # Load existing checkpoints
        self._load_existing_checkpoints()

        logger.info(f"CheckpointManager initialized with directory: {self.checkpoint_dir}")

    def create_checkpoint(self, version_id: str, version: Union[Dict[str, Any], Experiment]) -> str:
        """Create a checkpoint for a version.

        Args:
            version_id: Unique identifier for the version
            version: Version data (dict or Experiment object)

        Returns:
            Path to the created checkpoint

        Raises:
            CheckpointError: If checkpoint creation fails
        """
        try:
            # Convert version to dict if it's an Experiment object
            if isinstance(version, Experiment):
                version_data = version.to_dict()
                changes = version_data.get('artifacts', {})
                parent_id = version_data.get('parent_id')
                timestamp = version_data.get('created_at', datetime.now(timezone.utc).isoformat())
            elif isinstance(version, dict):
                version_data = version
                changes = version.get('changes', {})
                parent_id = version.get('parent_id')
                timestamp = version.get('timestamp', datetime.now(timezone.utc).isoformat())
            else:
                raise CheckpointError(f"Expected Experiment or dict, got {type(version)}")

            # Create checkpoint directory
            checkpoint_path = self.checkpoint_dir / f"checkpoint_{version_id}"
            checkpoint_path.mkdir(parents=True, exist_ok=True)

            # Save version data files
            if changes:
                for file_path, content in changes.items():
                    if isinstance(content, str):
                        full_path = checkpoint_path / file_path
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(full_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    elif isinstance(content, dict) and 'file_path' in content:
                        # Handle artifact references
                        src_path = Path(content['file_path'])
                        if src_path.exists():
                            dst_path = checkpoint_path / file_path
                            dst_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src_path, dst_path)

            # Save metadata
            metadata = {
                'version_id': version_id,
                'parent_id': parent_id,
                'timestamp': timestamp if isinstance(timestamp, str) else timestamp.isoformat(),
                'checkpoint_time': datetime.now(timezone.utc).isoformat(),
                'version_data': version_data,
                'file_count': len(changes) if changes else 0,
                'checkpoint_size': self._calculate_checkpoint_size(checkpoint_path),
            }

            metadata_path = checkpoint_path / 'metadata.json'
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)

            # Register checkpoint
            self.checkpoints[version_id] = str(checkpoint_path)

            # Auto-cleanup if enabled
            if self.auto_cleanup:
                self._cleanup_old_checkpoints()

            logger.info(f"Created checkpoint for version {version_id} at {checkpoint_path}")
            return str(checkpoint_path)

        except Exception as e:
            raise CheckpointError(
                f"Failed to create checkpoint for version {version_id}: {e}"
            ) from e

    def restore_checkpoint(self, version_id: str, target_dir: Union[str, Path]) -> bool:
        """Restore a checkpoint to the target directory.

        Args:
            version_id: ID of the version to restore
            target_dir: Directory to restore the checkpoint to

        Returns:
            True if restoration was successful

        Raises:
            CheckpointError: If restoration fails
        """
        try:
            target_dir = Path(target_dir)

            # Find checkpoint path
            if version_id not in self.checkpoints:
                checkpoint_path = self.checkpoint_dir / f"checkpoint_{version_id}"
                if not checkpoint_path.exists():
                    raise CheckpointError(f"Checkpoint for version {version_id} not found")
                self.checkpoints[version_id] = str(checkpoint_path)

            checkpoint_path = Path(self.checkpoints[version_id])

            # Verify checkpoint exists and has metadata
            metadata_path = checkpoint_path / 'metadata.json'
            if not metadata_path.exists():
                raise CheckpointError(f"Checkpoint metadata not found for version {version_id}")

            # Clear target directory (except .git and other protected directories)
            protected_dirs = {'.git', '.evoseal', '__pycache__', '.pytest_cache', 'node_modules'}
            if target_dir.exists():
                for item in target_dir.iterdir():
                    if item.name in protected_dirs:
                        continue
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

            # Copy checkpoint files to target directory
            for item in checkpoint_path.iterdir():
                if item.name == 'metadata.json':
                    continue  # Don't copy metadata file

                dst_path = target_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst_path, dirs_exist_ok=True)
                else:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dst_path)

            logger.info(f"Restored checkpoint {version_id} to {target_dir}")
            return True

        except Exception as e:
            raise CheckpointError(f"Failed to restore checkpoint {version_id}: {e}") from e

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all available checkpoints.

        Returns:
            List of checkpoint metadata dictionaries
        """
        checkpoints = []

        for item in self.checkpoint_dir.iterdir():
            if item.is_dir() and item.name.startswith('checkpoint_'):
                metadata_path = item / 'metadata.json'
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            checkpoints.append(metadata)
                    except (json.JSONDecodeError, OSError) as e:
                        logger.warning(f"Failed to read checkpoint metadata {metadata_path}: {e}")

        # Sort by checkpoint time
        return sorted(checkpoints, key=lambda x: x.get('checkpoint_time', ''))

    def get_checkpoint_path(self, version_id: str) -> Optional[str]:
        """Get the path to a checkpoint.

        Args:
            version_id: ID of the version

        Returns:
            Path to the checkpoint or None if not found
        """
        if version_id in self.checkpoints:
            return self.checkpoints[version_id]

        checkpoint_path = self.checkpoint_dir / f"checkpoint_{version_id}"
        if checkpoint_path.exists():
            self.checkpoints[version_id] = str(checkpoint_path)
            return str(checkpoint_path)

        return None

    def get_checkpoint_metadata(self, version_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a checkpoint.

        Args:
            version_id: ID of the version

        Returns:
            Checkpoint metadata or None if not found
        """
        checkpoint_path = self.get_checkpoint_path(version_id)
        if not checkpoint_path:
            return None

        metadata_path = Path(checkpoint_path) / 'metadata.json'
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read checkpoint metadata {metadata_path}: {e}")
            return None

    def delete_checkpoint(self, version_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            version_id: ID of the version to delete

        Returns:
            True if deletion was successful
        """
        checkpoint_path = self.get_checkpoint_path(version_id)
        if not checkpoint_path:
            return False

        try:
            shutil.rmtree(checkpoint_path)
            if version_id in self.checkpoints:
                del self.checkpoints[version_id]
            logger.info(f"Deleted checkpoint for version {version_id}")
            return True
        except OSError as e:
            logger.error(f"Failed to delete checkpoint {version_id}: {e}")
            return False

    def get_checkpoint_size(self, version_id: str) -> Optional[int]:
        """Get the size of a checkpoint in bytes.

        Args:
            version_id: ID of the version

        Returns:
            Size in bytes or None if checkpoint not found
        """
        checkpoint_path = self.get_checkpoint_path(version_id)
        if not checkpoint_path:
            return None

        return self._calculate_checkpoint_size(Path(checkpoint_path))

    def cleanup_old_checkpoints(self, keep_count: Optional[int] = None) -> int:
        """Clean up old checkpoints, keeping only the most recent ones.

        Args:
            keep_count: Number of checkpoints to keep (defaults to max_checkpoints)

        Returns:
            Number of checkpoints deleted
        """
        keep_count = keep_count or self.max_checkpoints
        checkpoints = self.list_checkpoints()

        if len(checkpoints) <= keep_count:
            return 0

        # Sort by checkpoint time and keep the most recent
        checkpoints.sort(key=lambda x: x.get('checkpoint_time', ''), reverse=True)
        to_delete = checkpoints[keep_count:]

        deleted_count = 0
        for checkpoint in to_delete:
            version_id = checkpoint.get('version_id')
            if version_id and self.delete_checkpoint(version_id):
                deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} old checkpoints")
        return deleted_count

    def _load_existing_checkpoints(self) -> None:
        """Load existing checkpoints into the registry."""
        if not self.checkpoint_dir.exists():
            return

        for item in self.checkpoint_dir.iterdir():
            if item.is_dir() and item.name.startswith('checkpoint_'):
                version_id = item.name.replace('checkpoint_', '')
                self.checkpoints[version_id] = str(item)

        logger.debug(f"Loaded {len(self.checkpoints)} existing checkpoints")

    def _calculate_checkpoint_size(self, checkpoint_path: Path) -> int:
        """Calculate the total size of a checkpoint directory."""
        total_size = 0
        try:
            for item in checkpoint_path.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
        except OSError:
            pass
        return total_size

    def _cleanup_old_checkpoints(self) -> None:
        """Automatically clean up old checkpoints if enabled."""
        if self.auto_cleanup and len(self.checkpoints) > self.max_checkpoints:
            self.cleanup_old_checkpoints()

    def get_stats(self) -> Dict[str, Any]:
        """Get checkpoint manager statistics.

        Returns:
            Dictionary with statistics about checkpoints
        """
        checkpoints = self.list_checkpoints()
        total_size = sum(
            self.get_checkpoint_size(cp.get('version_id', '')) or 0 for cp in checkpoints
        )

        return {
            'total_checkpoints': len(checkpoints),
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'checkpoint_directory': str(self.checkpoint_dir),
            'oldest_checkpoint': checkpoints[0].get('checkpoint_time') if checkpoints else None,
            'newest_checkpoint': checkpoints[-1].get('checkpoint_time') if checkpoints else None,
            'auto_cleanup_enabled': self.auto_cleanup,
            'max_checkpoints': self.max_checkpoints,
        }
