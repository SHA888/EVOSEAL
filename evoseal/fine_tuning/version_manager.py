"""
Model version manager for tracking and managing fine-tuned model versions.

This module handles versioning, rollback, and deployment of fine-tuned models
in the bidirectional evolution system.
"""

import asyncio
import hashlib
import json
import logging
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ModelVersionManager:
    """
    Manages versions of fine-tuned models.

    This class handles version tracking, rollback capabilities, and
    deployment management for fine-tuned local coding models.
    """

    def __init__(self, versions_dir: Path | None = None):
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

    def _load_registry(self) -> dict[str, Any]:
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
        training_results: dict[str, Any],
        validation_results: dict[str, Any] | None = None,
        data_prep_results: dict[str, Any] | None = None,
        version_name: str | None = None,
        *,
        deploy: bool = False,
        ollama_model_name: str | None = None,
    ) -> dict[str, Any]:
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

            # Generate version name if not provided. Derive a model-agnostic prefix
            # from the trained model's name (family slug) rather than hardcoding one.
            if not version_name:
                raw_name = str(training_results.get("model_name", "model"))
                slug = raw_name.split(":")[0].split("/")[-1] or "model"
                version_name = (
                    f"{slug}-v{len(self.registry['versions']) + 1}-{timestamp.strftime('%Y%m%d')}"
                )

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
                    shutil.copytree(model_path, version_dir / "model", dirs_exist_ok=True)
                    version_info["model_path"] = str((version_dir / "model").resolve())
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

            # Deploy to Ollama if requested and model files are available
            if deploy and version_info.get("model_path"):
                deploy_result = await self.deploy_version(
                    version_id, ollama_model_name=ollama_model_name
                )
                if "error" in deploy_result:
                    logger.warning(
                        f"Model registered but deployment failed: {deploy_result['error']}"
                    )
                    version_info["deployment_error"] = deploy_result["error"]
            elif deploy and not version_info.get("model_path"):
                version_info["deployment_error"] = "deploy requested but no model_path available"
                logger.warning(
                    f"Version {version_id}: deploy=True but no model_path; skipping deployment"
                )
                # NOTE: deploy_version mutates the same dict object that
                # get_version_info returns (it iterates self.registry["versions"]
                # and returns the matching entry by reference).  The deployment
                # fields (deployment_status, ollama_model_name, deployed_at) set
                # inside deploy_version are therefore visible here.  If
                # get_version_info is ever changed to return a *copy*, this
                # return value would silently omit those fields — callers
                # should then re-fetch via get_version_info after deploy.

            return version_info

        except Exception as e:
            logger.error(f"Error registering model version: {e}")
            return {"error": str(e)}

    def _generate_version_id(self, timestamp: datetime, training_results: dict[str, Any]) -> str:
        """Generate a unique version ID."""
        # Create hash from timestamp and training results
        content = (
            f"{timestamp.isoformat()}{json.dumps(training_results, sort_keys=True, default=str)}"
        )
        # Not a security hash -- just a short, stable id for the version folder.
        hash_object = hashlib.md5(content.encode(), usedforsecurity=False)
        return f"v{timestamp.strftime('%Y%m%d_%H%M%S')}_{hash_object.hexdigest()[:8]}"

    def _extract_performance_metrics(
        self,
        training_results: dict[str, Any],
        validation_results: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Extract key performance metrics from results."""
        metrics = {}

        # Training metrics
        if training_results:
            metrics["train_loss"] = training_results.get("train_loss")
            metrics["training_examples"] = training_results.get("training_examples_count")
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

    def get_version_info(self, version_id: str) -> dict[str, Any] | None:
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
        self, limit: int | None = None, status_filter: str | None = None
    ) -> list[dict[str, Any]]:
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

    def get_current_version(self) -> dict[str, Any] | None:
        """Get the current deployed version."""
        current_id = self.registry.get("current_version")
        if current_id:
            return self.get_version_info(current_id)
        return None

    async def deploy_version(
        self,
        version_id: str,
        ollama_model_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Deploy a registered model version to Ollama.

        Creates a Modelfile and runs ``ollama create`` so the serving layer
        (OllamaProvider) can load the fine-tuned model.

        Args:
            version_id: Version ID to deploy
            ollama_model_name: Ollama model name (default: version_name)

        Returns:
            Deployment result dict with 'ollama_model' on success or 'error'
        """
        version_info = self.get_version_info(version_id)
        if not version_info:
            return {"error": f"Version {version_id} not found"}

        model_path = version_info.get("model_path")
        if not model_path or not Path(model_path).exists():
            return {"error": f"Model files not found at {model_path}"}

        # Determine Ollama model name
        if not ollama_model_name:
            ollama_model_name = version_info.get("version_name", version_id)

        # Sanitize for Ollama: lowercase, alphanumeric + hyphens/underscores/dots only.
        sanitized = re.sub(r"[^a-z0-9._-]", "-", ollama_model_name.lower()).strip("-._")
        if not sanitized:
            sanitized = f"model-{version_id}"
        if sanitized != ollama_model_name:
            logger.info(f"Sanitized Ollama model name: {ollama_model_name!r} -> {sanitized!r}")
        ollama_model_name = sanitized

        # Guard against ollama_model_name collision with another version.
        # ollama create silently overwrites the tag, but the superseded
        # version's registry entry would still claim "deployed" under the
        # same name — making two entries look live for one tag.
        for other in self.registry["versions"]:
            if (
                other["version_id"] != version_id
                and other.get("ollama_model_name") == ollama_model_name
            ):
                other["deployment_status"] = "superseded"
                logger.info(
                    f"Marked version {other['version_id']} as superseded: "
                    f"Ollama model name '{ollama_model_name}' is being reused "
                    f"by version {version_id}"
                )

        # Create Modelfile
        try:
            modelfile_content = self._create_modelfile(model_path)
        except ValueError as e:
            version_info["deployment_status"] = "failed"
            version_info["deployment_error"] = str(e)
            self._save_registry()
            return {"error": str(e)}
        modelfile_path = self.versions_dir / version_id / "Modelfile"
        try:
            modelfile_path.parent.mkdir(parents=True, exist_ok=True)
            modelfile_path.write_text(modelfile_content)
        except OSError as e:
            version_info["deployment_status"] = "failed"
            version_info["deployment_error"] = f"Could not write Modelfile: {e}"
            self._save_registry()
            return {"error": f"Could not write Modelfile: {e}"}

        # Run ollama create (in a thread to avoid blocking the event loop)
        deploy_error = await asyncio.to_thread(
            self._deploy_to_ollama, ollama_model_name, modelfile_path
        )
        if deploy_error:
            # Update registry with failure
            version_info["deployment_status"] = "failed"
            version_info["deployment_error"] = deploy_error
            self._save_registry()
            return {"error": deploy_error}

        # Update registry with success
        version_info["deployment_status"] = "deployed"
        version_info["ollama_model_name"] = ollama_model_name
        version_info["deployed_at"] = datetime.now().isoformat()
        self._save_registry()

        # Clear the installed-model cache so resolve_model picks up the new model
        try:
            from evoseal.providers.local_models import clear_model_cache

            clear_model_cache()
        except ImportError:
            pass

        logger.info(f"Deployed version {version_id} as Ollama model '{ollama_model_name}'")
        return {
            "ollama_model": ollama_model_name,
            "version_id": version_id,
            "modelfile": str(modelfile_path),
        }

    @staticmethod
    def _validate_model_path(path: Path) -> None:
        """Raise ValueError if *path* contains characters that would break a Modelfile.

        Ollama Modelfiles use whitespace-delimited parsing for ``FROM`` and
        ``ADAPTER`` directives.  A path containing spaces, tabs, or newlines
        would silently split across tokens and produce a confusing parse error
        from ``ollama create`` rather than a clear deployment failure.
        """
        raw = str(path)
        if any(ch.isspace() for ch in raw):
            raise ValueError(
                f"Model path contains whitespace and cannot be used in a Modelfile: {raw!r}"
            )

    @staticmethod
    def _create_modelfile(model_path: str) -> str:
        """Generate a Modelfile for the given model directory.

        Handles two common formats:
        - GGUF files (``*.gguf``): direct ``FROM`` reference (largest file
          when multiple quantizations exist)
        - HuggingFace safetensors / adapter directories: ``FROM`` the directory
          (Ollama >= 0.4 supports ``FROM <dir>`` for safetensors models)
        - LoRA/PEFT adapter directories: ``FROM <base>`` + ``ADAPTER <path>``
          when an adapter config is detected

        Args:
            model_path: Path to the model files

        Returns:
            Modelfile content string

        Raises:
            ValueError: If *model_path* contains whitespace characters.
        """
        p = Path(model_path)

        # Validate paths up-front so a malformed path surfaces as a clear
        # error instead of a confusing ``ollama create`` parse failure.
        ModelVersionManager._validate_model_path(p)

        # Check for GGUF files first
        gguf_files = list(p.glob("*.gguf"))
        if gguf_files:
            # Pick the largest GGUF deterministically (avoids arbitrary
            # filesystem order when multiple quantizations exist).
            selected = max(gguf_files, key=lambda f: f.stat().st_size)
            ModelVersionManager._validate_model_path(selected)
            return f"FROM {selected}\n"

        # Detect LoRA/PEFT adapter directory — these need ADAPTER syntax,
        # not a bare FROM.  adapter_config.json is the canonical marker.
        if (p / "adapter_config.json").exists():
            try:
                with open(p / "adapter_config.json") as f:
                    cfg = json.load(f)
                base_model = cfg.get("base_model_name_or_path", "")
                if base_model:
                    return f"FROM {base_model}\nADAPTER {p}\n"
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"adapter_config.json found at {p} but could not be parsed: {e}")
            # If we can't read the config, fall through to FROM <dir> and
            # let ollama produce a clear error rather than silently breaking.
            logger.warning(
                f"adapter_config.json found at {p} but could not read base model"
                " — falling back to FROM <dir> which may not work"
            )

        # HuggingFace directory — point FROM at the directory itself
        return f"FROM {p}\n"

    @staticmethod
    def _deploy_to_ollama(model_name: str, modelfile_path: Path) -> str | None:
        """Run ``ollama create`` to register a model with Ollama.

        Args:
            model_name: Name for the new Ollama model
            modelfile_path: Path to the Modelfile

        Returns:
            None on success, error message string on failure.
        """
        try:
            result = subprocess.run(
                ["ollama", "create", model_name, "-f", str(modelfile_path)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip() or "unknown error"
                logger.error(f"ollama create failed: {error}")
                return error
            logger.info(f"ollama create succeeded for '{model_name}'")
            return None
        except FileNotFoundError:
            return "ollama CLI not found on PATH"
        except subprocess.TimeoutExpired:
            return "ollama create timed out after 300s"
        except OSError as e:
            return f"Could not run ollama create: {e}"

    def get_version_statistics(self) -> dict[str, Any]:
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

        # Deployment status distribution
        deploy_counts = {}
        for version in versions:
            deploy_status = version.get("deployment_status", "pending")
            deploy_counts[deploy_status] = deploy_counts.get(deploy_status, 0) + 1

        stats = {
            "total_versions": total_versions,
            "status_distribution": status_counts,
            "deployment_distribution": deploy_counts,
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

    def export_version_history(self, output_file: Path | None = None) -> Path:
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
