"""
Model version manager for tracking and managing fine-tuned model versions.

This module handles versioning, rollback, and deployment of fine-tuned models
in the bidirectional evolution system.
"""

import hashlib
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModelVersionManager:
    """
    Manages versions of fine-tuned models.

    This class handles version tracking, rollback capabilities, and
    deployment management for fine-tuned Devstral models.
    """

    def __init__(self, versions_dir: Optional[Path] = None):
        """
        Initialize the model version manager.

        Args:
            versions_dir: Directory to store model versions
        """
        self.versions_dir = versions_dir or Path("models/versions")
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        # Version registry file
        self.registry_file = self.versions_dir / "version_registry.json"

        # Load existing registry
        self.registry = self._load_registry()

        logger.info(
            f"ModelVersionManager initialized with {len(self.registry.get('versions', []))} versions"
        )

    def _load_registry(self) -> Dict[str, Any]:
        """Load the version registry from disk."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading version registry: {e}")
                return {
                    "versions": [],
                    "current_version": None,
                    "created": datetime.now().isoformat(),
                }
        else:
            return {
                "versions": [],
                "current_version": None,
                "created": datetime.now().isoformat(),
            }

    def _save_registry(self) -> None:
        """Save the version registry to disk."""
        try:
            self.registry["updated"] = datetime.now().isoformat()
            with open(self.registry_file, "w") as f:
                json.dump(self.registry, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving version registry: {e}")

    async def register_version(
        self,
        training_results: Dict[str, Any],
        validation_results: Optional[Dict[str, Any]] = None,
        data_prep_results: Optional[Dict[str, Any]] = None,
        version_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a new model version.

        Args:
            training_results: Results from model training
            validation_results: Results from model validation
            data_prep_results: Results from data preparation
            version_name: Optional custom version name

        Returns:
            Version information
        """
        try:
            timestamp = datetime.now()

            # Generate version ID
            version_id = self._generate_version_id(timestamp, training_results)

            # Generate version name if not provided
            if not version_name:
                version_name = f"devstral-v{len(self.registry['versions']) + 1}-{timestamp.strftime('%Y%m%d')}"

            # Create version entry
            version_info = {
                "version_id": version_id,
                "version_name": version_name,
                "timestamp": timestamp.isoformat(),
                "training_results": training_results,
                "validation_results": validation_results,
                "data_prep_results": data_prep_results,
                "status": "registered",
                "deployment_status": "pending",
                "performance_metrics": self._extract_performance_metrics(
                    training_results, validation_results
                ),
            }

            # Copy model files if available
            model_path = training_results.get("model_save_path")
            if model_path and Path(model_path).exists():
                version_dir = self.versions_dir / version_id
                version_dir.mkdir(parents=True, exist_ok=True)

                # Copy model files
                try:
                    shutil.copytree(
                        model_path, version_dir / "model", dirs_exist_ok=True
                    )
                    version_info["model_path"] = str(version_dir / "model")
                    version_info["status"] = "stored"
                except Exception as e:
                    logger.warning(f"Could not copy model files: {e}")
                    version_info["model_path"] = model_path

            # Add to registry
            self.registry["versions"].append(version_info)

            # Set as current version if it's the first or if validation passed
            if not self.registry["current_version"] or (
                validation_results and validation_results.get("passed", False)
            ):
                self.registry["current_version"] = version_id
                version_info["deployment_status"] = "current"

            # Save registry
            self._save_registry()

            logger.info(f"Registered model version {version_id} ({version_name})")
            return version_info

        except Exception as e:
            logger.error(f"Error registering model version: {e}")
            return {"error": str(e)}

    def _generate_version_id(
        self, timestamp: datetime, training_results: Dict[str, Any]
    ) -> str:
        """Generate a unique version ID."""
        # Create hash from timestamp and training results
        content = f"{timestamp.isoformat()}{json.dumps(training_results, sort_keys=True, default=str)}"
        hash_object = hashlib.md5(content.encode())
        return f"v{timestamp.strftime('%Y%m%d_%H%M%S')}_{hash_object.hexdigest()[:8]}"

    def _extract_performance_metrics(
        self,
        training_results: Dict[str, Any],
        validation_results: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Extract key performance metrics from results."""
        metrics = {}

        # Training metrics
        if training_results:
            metrics["train_loss"] = training_results.get("train_loss")
            metrics["training_examples"] = training_results.get(
                "training_examples_count"
            )
            metrics["fallback_mode"] = training_results.get("fallback_mode", False)

        # Validation metrics
        if validation_results:
            metrics["validation_score"] = validation_results.get("overall_score")
            metrics["validation_passed"] = validation_results.get("passed", False)

            # Extract test scores
            test_results = validation_results.get("test_results", {})
            for test_name, result in test_results.items():
                if isinstance(result, dict) and "score" in result:
                    metrics[f"{test_name}_score"] = result["score"]

        return metrics

    def get_version_info(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific version.

        Args:
            version_id: Version ID to look up

        Returns:
            Version information or None if not found
        """
        for version in self.registry["versions"]:
            if version["version_id"] == version_id:
                return version
        return None

    def list_versions(
        self, limit: Optional[int] = None, status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List model versions.

        Args:
            limit: Maximum number of versions to return
            status_filter: Filter by status (registered, stored, deployed)

        Returns:
            List of version information
        """
        versions = self.registry["versions"]

        # Apply status filter
        if status_filter:
            versions = [v for v in versions if v.get("status") == status_filter]

        # Sort by timestamp (newest first)
        versions = sorted(versions, key=lambda x: x["timestamp"], reverse=True)

        # Apply limit
        if limit:
            versions = versions[:limit]

        return versions

    def get_current_version(self) -> Optional[Dict[str, Any]]:
        """Get the current deployed version."""
        current_id = self.registry.get("current_version")
        if current_id:
            return self.get_version_info(current_id)
        return None

    def get_version_statistics(self) -> Dict[str, Any]:
        """Get statistics about model versions."""
        versions = self.registry["versions"]

        if not versions:
            return {"total_versions": 0}

        # Calculate statistics
        total_versions = len(versions)

        # Status distribution
        status_counts = {}
        for version in versions:
            status = version.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        # Performance trends (if available)
        validation_scores = []
        for version in versions:
            score = version.get("performance_metrics", {}).get("validation_score")
            if score is not None:
                validation_scores.append(score)

        stats = {
            "total_versions": total_versions,
            "status_distribution": status_counts,
            "current_version": self.registry.get("current_version"),
            "registry_created": self.registry.get("created"),
            "registry_updated": self.registry.get("updated"),
        }

        if validation_scores:
            stats["performance_trends"] = {
                "avg_validation_score": sum(validation_scores) / len(validation_scores),
                "best_validation_score": max(validation_scores),
                "worst_validation_score": min(validation_scores),
                "total_evaluated": len(validation_scores),
            }

        return stats

    def export_version_history(self, output_file: Optional[Path] = None) -> Path:
        """
        Export version history to a file.

        Args:
            output_file: Optional output file path

        Returns:
            Path to the exported file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.versions_dir / f"version_history_{timestamp}.json"

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "registry": self.registry,
            "statistics": self.get_version_statistics(),
        }

        with open(output_file, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Version history exported to {output_file}")
        return output_file
