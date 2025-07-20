"""Checkpoint management system for EVOSEAL evolution pipeline.

This module provides comprehensive checkpoint management capabilities including
creation, restoration, listing, and metadata management for version control
and experiment tracking integration.
"""

import gzip
import hashlib
import json
import os
import pickle  # nosec B403 - Used for internal system state serialization only
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

    def create_checkpoint(
        self,
        version_id: str,
        version: Union[Dict[str, Any], Experiment],
        capture_system_state: bool = True,
    ) -> str:
        """Create a comprehensive checkpoint for a version.

        Args:
            version_id: Unique identifier for the version
            version: Version data (dict or Experiment object)
            capture_system_state: Whether to capture complete system state

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
                config = version_data.get('config', {})
                metrics = version_data.get('metrics', [])
                result = version_data.get('result', {})
            elif isinstance(version, dict):
                version_data = version
                changes = version.get('changes', {})
                parent_id = version.get('parent_id')
                timestamp = version.get('timestamp', datetime.now(timezone.utc).isoformat())
                config = version.get('config', {})
                metrics = version.get('metrics', [])
                result = version.get('result', {})
            else:
                raise CheckpointError(f"Expected Experiment or dict, got {type(version)}")

            # Create checkpoint directory
            checkpoint_path = self.checkpoint_dir / f"checkpoint_{version_id}"
            checkpoint_path.mkdir(parents=True, exist_ok=True)

            # Capture complete system state
            system_state = {}
            if capture_system_state:
                system_state = self._capture_system_state(version_data, config, metrics, result)

                # Save system state with compression if enabled
                state_file = checkpoint_path / 'system_state.pkl'
                if self.compression_enabled:
                    with gzip.open(f"{state_file}.gz", 'wb') as f:
                        pickle.dump(system_state, f)
                    state_file = f"{state_file}.gz"
                else:
                    with open(state_file, 'wb') as f:
                        pickle.dump(system_state, f)

            # Save version data files
            if changes:
                for file_path, content in changes.items():
                    if isinstance(content, str):
                        full_path = checkpoint_path / file_path
                        full_path.parent.mkdir(parents=True, exist_ok=True)

                        # Write with optional compression
                        if self.compression_enabled and full_path.suffix in [
                            '.json',
                            '.txt',
                            '.py',
                            '.md',
                        ]:
                            with gzip.open(f"{full_path}.gz", 'wt', encoding='utf-8') as f:
                                f.write(content)
                        else:
                            with open(full_path, 'w', encoding='utf-8') as f:
                                f.write(content)

                    elif isinstance(content, dict) and 'file_path' in content:
                        # Handle artifact references
                        src_path = Path(content['file_path'])
                        if src_path.exists():
                            dst_path = checkpoint_path / file_path
                            dst_path.parent.mkdir(parents=True, exist_ok=True)

                            # Copy with optional compression for text files
                            if self.compression_enabled and src_path.suffix in [
                                '.json',
                                '.txt',
                                '.py',
                                '.md',
                            ]:
                                with (
                                    open(src_path, 'rb') as src,
                                    gzip.open(f"{dst_path}.gz", 'wb') as dst,
                                ):
                                    dst.write(src.read())
                            else:
                                shutil.copy2(src_path, dst_path)

            # Calculate checkpoint size first
            checkpoint_size = self._calculate_checkpoint_size(checkpoint_path)

            # Save comprehensive metadata (without integrity hash first)
            metadata = {
                'version_id': version_id,
                'parent_id': parent_id,
                'timestamp': timestamp if isinstance(timestamp, str) else timestamp.isoformat(),
                'checkpoint_time': datetime.now(timezone.utc).isoformat(),
                'version_data': version_data,
                'system_state_captured': capture_system_state,
                'compression_enabled': self.compression_enabled,
                'file_count': len(changes) if changes else 0,
                'checkpoint_size': checkpoint_size,
                'config_snapshot': config,
                'metrics_count': len(metrics) if metrics else 0,
                'has_results': bool(result),
            }

            metadata_path = checkpoint_path / 'metadata.json'
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)

            # Calculate integrity hash after all files are saved
            integrity_hash = self._calculate_integrity_hash(checkpoint_path)

            # Update metadata with integrity hash
            metadata['integrity_hash'] = integrity_hash
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)

            # Register checkpoint
            self.checkpoints[version_id] = str(checkpoint_path)

            # Auto-cleanup if enabled
            if self.auto_cleanup:
                self._cleanup_old_checkpoints()

            logger.info(
                f"Created comprehensive checkpoint for version {version_id} at {checkpoint_path}"
            )
            logger.info(
                f"Checkpoint size: {checkpoint_size / (1024*1024):.2f} MB, Integrity: {integrity_hash[:8]}..."
            )
            return str(checkpoint_path)

        except Exception as e:
            raise CheckpointError(
                f"Failed to create checkpoint for version {version_id}: {e}"
            ) from e

    def restore_checkpoint(
        self, version_id: str, target_dir: Union[str, Path], verify_integrity: bool = True
    ) -> Dict[str, Any]:
        """Restore a checkpoint to the target directory with integrity verification.

        Args:
            version_id: ID of the version to restore
            target_dir: Directory to restore the checkpoint to
            verify_integrity: Whether to verify checkpoint integrity before restoration

        Returns:
            Dictionary with restoration results and system state

        Raises:
            CheckpointError: If restoration fails
        """
        try:
            target_dir = Path(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            # Find checkpoint path
            if version_id not in self.checkpoints:
                checkpoint_path = self.checkpoint_dir / f"checkpoint_{version_id}"
                if not checkpoint_path.exists():
                    raise CheckpointError(f"Checkpoint for version {version_id} not found")
                self.checkpoints[version_id] = str(checkpoint_path)

            checkpoint_path = Path(self.checkpoints[version_id])

            # Load and verify metadata
            metadata_path = checkpoint_path / 'metadata.json'
            if not metadata_path.exists():
                raise CheckpointError(f"Checkpoint metadata not found for version {version_id}")

            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # Verify integrity if requested
            if verify_integrity:
                logger.info(f"Verifying integrity of checkpoint {version_id}...")
                if not self.verify_checkpoint_integrity(version_id):
                    raise CheckpointError(
                        f"Integrity verification failed for checkpoint {version_id}"
                    )
                logger.info("Integrity verification passed")

            # Clear target directory (except protected directories)
            protected_dirs = {'.git', '.evoseal', '__pycache__', '.pytest_cache', 'node_modules'}
            if target_dir.exists():
                for item in target_dir.iterdir():
                    if item.name in protected_dirs:
                        continue
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

            # Restore files with decompression support
            restored_files = 0
            compression_enabled = metadata.get('compression_enabled', False)

            for item in checkpoint_path.iterdir():
                if item.name in ['metadata.json', 'system_state.pkl', 'system_state.pkl.gz']:
                    continue  # Skip metadata and system state files

                dst_path = target_dir / item.name

                if item.is_dir():
                    shutil.copytree(item, dst_path, dirs_exist_ok=True)
                    restored_files += len(list(item.rglob('*')))
                else:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)

                    # Handle compressed files
                    if item.suffix == '.gz' and compression_enabled:
                        # Decompress file
                        original_name = item.stem
                        decompressed_path = target_dir / original_name
                        decompressed_path.parent.mkdir(parents=True, exist_ok=True)

                        try:
                            with gzip.open(item, 'rb') as src:
                                with open(decompressed_path, 'wb') as dst:
                                    dst.write(src.read())
                            restored_files += 1
                        except Exception as e:
                            logger.warning(f"Failed to decompress {item}: {e}")
                            # Fallback to copying compressed file
                            shutil.copy2(item, dst_path)
                            restored_files += 1
                    else:
                        shutil.copy2(item, dst_path)
                        restored_files += 1

            # Restore system state if available
            system_state = None
            state_file = checkpoint_path / 'system_state.pkl'
            state_file_gz = checkpoint_path / 'system_state.pkl.gz'

            if state_file_gz.exists():
                try:
                    with gzip.open(state_file_gz, 'rb') as f:
                        system_state = pickle.load(f)  # nosec B301 - Internal checkpoint data only
                    logger.info("Restored compressed system state")
                except Exception as e:
                    logger.warning(f"Failed to restore compressed system state: {e}")
            elif state_file.exists():
                try:
                    with open(state_file, 'rb') as f:
                        system_state = pickle.load(f)  # nosec B301 - Internal checkpoint data only
                    logger.info("Restored system state")
                except Exception as e:
                    logger.warning(f"Failed to restore system state: {e}")

            restoration_result = {
                'success': True,
                'version_id': version_id,
                'target_directory': str(target_dir),
                'restored_files': restored_files,
                'system_state': system_state,
                'metadata': metadata,
                'integrity_verified': verify_integrity,
                'restoration_time': datetime.now(timezone.utc).isoformat(),
            }

            logger.info(f"Successfully restored checkpoint {version_id} to {target_dir}")
            logger.info(
                f"Restored {restored_files} files, System state: {'Yes' if system_state else 'No'}"
            )
            return restoration_result

        except Exception as e:
            logger.error(f"Failed to restore checkpoint {version_id}: {e}")
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

    def _capture_system_state(
        self,
        version_data: Dict[str, Any],
        config: Dict[str, Any],
        metrics: List[Dict[str, Any]],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Capture complete system state including model parameters and configuration.

        Args:
            version_data: Version data dictionary
            config: Configuration dictionary
            metrics: List of metrics
            result: Result dictionary

        Returns:
            Complete system state dictionary
        """
        import platform
        import sys

        import psutil

        try:
            # Capture system environment
            system_info = {
                'python_version': sys.version,
                'platform': platform.platform(),
                'architecture': platform.architecture(),
                'processor': platform.processor(),
                'memory_total': psutil.virtual_memory().total,
                'memory_available': psutil.virtual_memory().available,
                'cpu_count': psutil.cpu_count(),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning(f"Failed to capture system info: {e}")
            system_info = {'error': str(e)}

        # Capture model parameters if available
        model_state = {}
        if config:
            # Extract model-related parameters
            model_params = {
                'learning_rate': config.get('learning_rate'),
                'batch_size': config.get('batch_size'),
                'epochs': config.get('epochs'),
                'model_architecture': config.get('model_architecture'),
                'optimizer': config.get('optimizer'),
                'loss_function': config.get('loss_function'),
                'hyperparameters': config.get('hyperparameters', {}),
            }
            # Remove None values
            model_state = {k: v for k, v in model_params.items() if v is not None}

        # Capture evolution state if available
        evolution_state = {}
        if result:
            evolution_state = {
                'best_fitness': result.get('best_fitness'),
                'generations_completed': result.get('generations_completed', 0),
                'total_evaluations': result.get('total_evaluations', 0),
                'convergence_iteration': result.get('convergence_iteration'),
                'execution_time': result.get('execution_time'),
                'memory_peak': result.get('memory_peak'),
                'cpu_usage': result.get('cpu_usage'),
            }

        # Capture metrics summary
        metrics_summary = {}
        if metrics:
            # Ensure metrics is a list of dictionaries
            if isinstance(metrics, list) and all(isinstance(m, dict) for m in metrics):
                metrics_summary = {
                    'total_metrics': len(metrics),
                    'metric_types': list(set(m.get('metric_type', 'unknown') for m in metrics)),
                    'latest_values': {
                        m.get('name'): m.get('value') for m in metrics[-10:] if m.get('name')
                    },
                    'timestamp_range': (
                        {
                            'earliest': min(
                                m.get('timestamp', '') for m in metrics if m.get('timestamp')
                            ),
                            'latest': max(
                                m.get('timestamp', '') for m in metrics if m.get('timestamp')
                            ),
                        }
                        if metrics
                        else None
                    ),
                }
            else:
                # Handle case where metrics is not in expected format
                metrics_summary = {
                    'total_metrics': 0,
                    'metric_types': [],
                    'latest_values': {},
                    'timestamp_range': None,
                    'warning': f'Metrics not in expected format: {type(metrics)}'
                }

        return {
            'system_info': system_info,
            'model_state': model_state,
            'evolution_state': evolution_state,
            'metrics_summary': metrics_summary,
            'version_metadata': {
                'version_id': version_data.get('id'),
                'name': version_data.get('name'),
                'description': version_data.get('description'),
                'tags': version_data.get('tags', []),
                'status': version_data.get('status'),
                'experiment_type': version_data.get('type'),
            },
            'capture_timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def _calculate_integrity_hash(self, checkpoint_path: Path) -> str:
        """Calculate SHA-256 hash of all files in checkpoint for integrity verification.

        Args:
            checkpoint_path: Path to checkpoint directory

        Returns:
            SHA-256 hash string
        """
        hasher = hashlib.sha256()

        try:
            # Sort files for consistent hashing
            files = sorted(checkpoint_path.rglob('*'))

            for file_path in files:
                if file_path.is_file():
                    # Skip metadata.json to avoid circular dependency
                    if file_path.name == 'metadata.json':
                        continue

                    # Include file path in hash for structure integrity
                    relative_path = file_path.relative_to(checkpoint_path)
                    hasher.update(str(relative_path).encode('utf-8'))

                    # Include file content
                    try:
                        if file_path.suffix == '.gz':
                            with gzip.open(file_path, 'rb') as f:
                                hasher.update(f.read())
                        else:
                            with open(file_path, 'rb') as f:
                                hasher.update(f.read())
                    except Exception as e:
                        logger.warning(f"Failed to hash file {file_path}: {e}")
                        hasher.update(f"ERROR:{e}".encode('utf-8'))

        except Exception as e:
            logger.error(f"Failed to calculate integrity hash: {e}")
            hasher.update(f"HASH_ERROR:{e}".encode('utf-8'))

        return hasher.hexdigest()

    def verify_checkpoint_integrity(self, version_id: str) -> bool:
        """Verify the integrity of a checkpoint.

        Args:
            version_id: ID of the version to verify

        Returns:
            True if integrity check passes
        """
        try:
            metadata = self.get_checkpoint_metadata(version_id)
            if not metadata:
                logger.error(f"No metadata found for checkpoint {version_id}")
                return False

            stored_hash = metadata.get('integrity_hash')
            if not stored_hash:
                logger.warning(f"No integrity hash stored for checkpoint {version_id}")
                return True  # No hash to verify against

            checkpoint_path = Path(self.get_checkpoint_path(version_id))
            current_hash = self._calculate_integrity_hash(checkpoint_path)

            if current_hash == stored_hash:
                logger.info(f"Integrity verification passed for checkpoint {version_id}")
                return True
            else:
                logger.error(f"Integrity verification failed for checkpoint {version_id}")
                logger.error(f"Expected: {stored_hash}")
                logger.error(f"Actual: {current_hash}")
                return False

        except Exception as e:
            logger.error(f"Error during integrity verification: {e}")
            return False

    def restore_checkpoint_with_validation(
        self, version_id: str, target_dir: Union[str, Path], backup_current: bool = True
    ) -> Dict[str, Any]:
        """Restore checkpoint with comprehensive validation and optional backup.

        Args:
            version_id: ID of the version to restore
            target_dir: Directory to restore the checkpoint to
            backup_current: Whether to backup current state before restoration

        Returns:
            Dictionary with restoration results and validation status

        Raises:
            CheckpointError: If restoration fails
        """
        try:
            target_dir = Path(target_dir)
            restoration_start = datetime.now(timezone.utc)

            logger.info(
                f"Starting validated restoration of checkpoint {version_id} to {target_dir}"
            )

            # Pre-restoration validation
            validation_results = self.validate_checkpoint_for_restoration(version_id)
            if not validation_results['valid']:
                raise CheckpointError(
                    f"Checkpoint validation failed: {validation_results['errors']}"
                )

            # Backup current state if requested
            backup_path = None
            if backup_current and target_dir.exists():
                backup_path = self._create_restoration_backup(target_dir)
                logger.info(f"Created backup of current state at {backup_path}")

            # Perform restoration
            try:
                restoration_result = self.restore_checkpoint(
                    version_id, target_dir, verify_integrity=True
                )

                # Post-restoration validation
                post_validation = self._validate_restored_state(target_dir, version_id)

                result = {
                    'success': True,
                    'version_id': version_id,
                    'target_directory': str(target_dir),
                    'restoration_time': (
                        datetime.now(timezone.utc) - restoration_start
                    ).total_seconds(),
                    'backup_created': backup_path is not None,
                    'backup_path': str(backup_path) if backup_path else None,
                    'pre_validation': validation_results,
                    'post_validation': post_validation,
                    'restoration_details': restoration_result,
                }

                logger.info(f"Successfully completed validated restoration of {version_id}")
                return result

            except Exception as e:
                # Restoration failed - restore backup if available
                if backup_path and backup_path.exists():
                    logger.warning(f"Restoration failed, attempting to restore backup: {e}")
                    self._restore_from_backup(backup_path, target_dir)
                    logger.info("Successfully restored from backup")
                raise

        except Exception as e:
            logger.error(f"Validated restoration failed for {version_id}: {e}")
            raise CheckpointError(f"Validated restoration failed: {e}") from e

    def validate_checkpoint_for_restoration(self, version_id: str) -> Dict[str, Any]:
        """Validate that a checkpoint is ready for restoration.

        Args:
            version_id: ID of the version to validate

        Returns:
            Dictionary with validation results
        """
        validation_errors = []
        validation_warnings = []

        try:
            # Check if checkpoint exists
            checkpoint_path = self.get_checkpoint_path(version_id)
            if not checkpoint_path:
                validation_errors.append(f"Checkpoint {version_id} not found")
                return {
                    'valid': False,
                    'errors': validation_errors,
                    'warnings': validation_warnings,
                }

            checkpoint_path = Path(checkpoint_path)

            # Check metadata exists
            metadata_path = checkpoint_path / 'metadata.json'
            if not metadata_path.exists():
                validation_errors.append("Checkpoint metadata missing")
            else:
                # Validate metadata content
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)

                    required_fields = ['version_id', 'timestamp', 'file_count']
                    for field in required_fields:
                        if field not in metadata:
                            validation_warnings.append(f"Missing metadata field: {field}")

                except Exception as e:
                    validation_errors.append(f"Invalid metadata format: {e}")

            # Check integrity if hash is available
            if not validation_errors:
                try:
                    integrity_valid = self.verify_checkpoint_integrity(version_id)
                    if not integrity_valid:
                        validation_errors.append("Checkpoint integrity verification failed")
                except Exception as e:
                    validation_warnings.append(f"Could not verify integrity: {e}")

            # Check disk space
            checkpoint_size = self.get_checkpoint_size(version_id)
            if checkpoint_size:
                available_space = shutil.disk_usage(checkpoint_path.parent).free
                if checkpoint_size > available_space:
                    validation_errors.append(f"Insufficient disk space for restoration")
                elif checkpoint_size > available_space * 0.9:  # 90% threshold
                    validation_warnings.append("Low disk space for restoration")

            return {
                'valid': len(validation_errors) == 0,
                'errors': validation_errors,
                'warnings': validation_warnings,
                'checkpoint_size': checkpoint_size,
                'validation_time': datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            validation_errors.append(f"Validation error: {e}")
            return {'valid': False, 'errors': validation_errors, 'warnings': validation_warnings}

    def _create_restoration_backup(self, target_dir: Path) -> Path:
        """Create a backup of the current state before restoration.

        Args:
            target_dir: Directory to backup

        Returns:
            Path to the backup directory
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        backup_dir = self.checkpoint_dir / 'restoration_backups'
        backup_dir.mkdir(parents=True, exist_ok=True)

        backup_path = backup_dir / f"backup_{target_dir.name}_{timestamp}"

        # Copy current state to backup
        shutil.copytree(target_dir, backup_path, dirs_exist_ok=True)

        # Create backup metadata
        backup_metadata = {
            'original_path': str(target_dir),
            'backup_time': datetime.now(timezone.utc).isoformat(),
            'backup_size': self._calculate_checkpoint_size(backup_path),
        }

        with open(backup_path / 'backup_metadata.json', 'w', encoding='utf-8') as f:
            json.dump(backup_metadata, f, indent=2)

        return backup_path

    def _restore_from_backup(self, backup_path: Path, target_dir: Path) -> None:
        """Restore from a backup directory.

        Args:
            backup_path: Path to backup directory
            target_dir: Target directory to restore to
        """
        # Clear target directory
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # Copy backup to target
        shutil.copytree(backup_path, target_dir, dirs_exist_ok=True)

        # Remove backup metadata from restored directory
        backup_metadata_path = target_dir / 'backup_metadata.json'
        if backup_metadata_path.exists():
            backup_metadata_path.unlink()

    def _validate_restored_state(self, target_dir: Path, version_id: str) -> Dict[str, Any]:
        """Validate the state after restoration.

        Args:
            target_dir: Directory that was restored to
            version_id: Version ID that was restored

        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'directory_exists': target_dir.exists(),
            'files_present': [],
            'validation_time': datetime.now(timezone.utc).isoformat(),
        }

        if target_dir.exists():
            # Count restored files
            restored_files = list(target_dir.rglob('*'))
            validation_results['file_count'] = len([f for f in restored_files if f.is_file()])
            validation_results['directory_count'] = len([f for f in restored_files if f.is_dir()])

            # Check for key files
            key_files = ['main.py', 'config.json', 'README.md']
            for key_file in key_files:
                file_path = target_dir / key_file
                validation_results['files_present'].append(
                    {
                        'file': key_file,
                        'exists': file_path.exists(),
                        'size': file_path.stat().st_size if file_path.exists() else 0,
                    }
                )

        return validation_results

    def list_restoration_backups(self) -> List[Dict[str, Any]]:
        """List available restoration backups.

        Returns:
            List of backup information dictionaries
        """
        backup_dir = self.checkpoint_dir / 'restoration_backups'
        backups = []

        if backup_dir.exists():
            for backup_path in backup_dir.iterdir():
                if backup_path.is_dir():
                    metadata_path = backup_path / 'backup_metadata.json'
                    if metadata_path.exists():
                        try:
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)

                            backup_info = {
                                'backup_name': backup_path.name,
                                'backup_path': str(backup_path),
                                'original_path': metadata.get('original_path'),
                                'backup_time': metadata.get('backup_time'),
                                'backup_size': metadata.get('backup_size', 0),
                                'age_hours': (
                                    datetime.now(timezone.utc)
                                    - datetime.fromisoformat(
                                        metadata.get('backup_time', '').replace('Z', '+00:00')
                                    )
                                ).total_seconds()
                                / 3600,
                            }
                            backups.append(backup_info)
                        except Exception as e:
                            logger.warning(f"Could not read backup metadata for {backup_path}: {e}")

        return sorted(backups, key=lambda x: x.get('backup_time', ''), reverse=True)

    def cleanup_restoration_backups(self, keep_count: int = 5, max_age_days: int = 30) -> int:
        """Clean up old restoration backups.

        Args:
            keep_count: Number of recent backups to keep
            max_age_days: Maximum age of backups to keep in days

        Returns:
            Number of backups deleted
        """
        backups = self.list_restoration_backups()
        deleted_count = 0

        # Sort by backup time (newest first)
        backups_by_time = sorted(backups, key=lambda x: x.get('backup_time', ''), reverse=True)

        for i, backup in enumerate(backups_by_time):
            should_delete = False

            # Delete if beyond keep count
            if i >= keep_count:
                should_delete = True
                logger.info(f"Deleting backup {backup['backup_name']} (beyond keep count)")

            # Delete if too old
            elif backup.get('age_hours', 0) > max_age_days * 24:
                should_delete = True
                logger.info(
                    f"Deleting backup {backup['backup_name']} (too old: {backup.get('age_hours', 0):.1f} hours)"
                )

            if should_delete:
                try:
                    backup_path = Path(backup['backup_path'])
                    if backup_path.exists():
                        shutil.rmtree(backup_path)
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup['backup_name']}: {e}")

        logger.info(f"Cleaned up {deleted_count} restoration backups")
        return deleted_count
