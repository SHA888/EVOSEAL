"""Experiment database for storing and querying experiments.

This module provides a database interface for storing, retrieving,
and querying experiments with their configurations, metrics, and results.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..models.experiment import (
    Experiment,
    ExperimentConfig,
    ExperimentMetric,
    ExperimentResult,
    ExperimentStatus,
    ExperimentType,
    MetricType,
)

logger = logging.getLogger(__name__)


class ExperimentDatabaseError(Exception):
    """Base exception for experiment database errors."""

    pass


class ExperimentNotFoundError(ExperimentDatabaseError):
    """Raised when an experiment is not found."""

    pass


class ExperimentDatabase:
    """Database for storing and querying experiments."""

    def __init__(self, db_path: Union[str, Path] = ":memory:"):
        """Initialize the experiment database.

        Args:
            db_path: Path to the SQLite database file, or ":memory:" for in-memory database
        """
        self.db_path = Path(db_path) if db_path != ":memory:" else db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            if self.db_path != ":memory:":
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _initialize_database(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()

        # Create experiments table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                experiment_type TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                config_json TEXT NOT NULL,
                result_json TEXT,
                git_commit TEXT,
                git_branch TEXT,
                git_repository TEXT,
                code_version TEXT,
                parent_experiment_id TEXT,
                created_by TEXT,
                tags_json TEXT,
                metadata_json TEXT,
                FOREIGN KEY (parent_experiment_id) REFERENCES experiments (id)
            )
        """
        )

        # Create metrics table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiment_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT NOT NULL,  -- JSON serialized value
                metric_type TEXT,
                timestamp TEXT NOT NULL,
                iteration INTEGER,
                step INTEGER,
                metadata_json TEXT,
                FOREIGN KEY (experiment_id) REFERENCES experiments (id) ON DELETE CASCADE
            )
        """
        )

        # Create artifacts table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiment_artifacts (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                name TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                file_path TEXT,
                content TEXT,
                size_bytes INTEGER,
                checksum TEXT,
                created_at TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY (experiment_id) REFERENCES experiments (id) ON DELETE CASCADE
            )
        """
        )

        # Create indexes for better query performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments (status)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_experiments_type ON experiments (experiment_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_experiments_created_at ON experiments (created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_experiments_created_by ON experiments (created_by)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_experiment_id ON experiment_metrics (experiment_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON experiment_metrics (name)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_artifacts_experiment_id ON experiment_artifacts (experiment_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_artifacts_type ON experiment_artifacts (artifact_type)"
        )

        conn.commit()

    def save_experiment(self, experiment: Experiment) -> None:
        """Save an experiment to the database.

        Args:
            experiment: Experiment to save
        """
        conn = self._get_connection()

        try:
            # Save main experiment record
            conn.execute(
                """
                INSERT OR REPLACE INTO experiments (
                    id, name, description, status, experiment_type,
                    created_at, started_at, completed_at, updated_at,
                    config_json, result_json, git_commit, git_branch,
                    git_repository, code_version, parent_experiment_id,
                    created_by, tags_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    experiment.id,
                    experiment.name,
                    experiment.description,
                    experiment.status.value,
                    experiment.config.experiment_type.value,
                    experiment.created_at.isoformat(),
                    experiment.started_at.isoformat() if experiment.started_at else None,
                    experiment.completed_at.isoformat() if experiment.completed_at else None,
                    experiment.updated_at.isoformat(),
                    experiment.config.model_dump_json(),
                    experiment.result.model_dump_json() if experiment.result else None,
                    experiment.git_commit,
                    experiment.git_branch,
                    experiment.git_repository,
                    experiment.code_version,
                    experiment.parent_experiment_id,
                    experiment.created_by,
                    json.dumps(experiment.tags),
                    json.dumps(experiment.metadata),
                ),
            )

            # Clear existing metrics and artifacts for this experiment
            conn.execute("DELETE FROM experiment_metrics WHERE experiment_id = ?", (experiment.id,))
            conn.execute(
                "DELETE FROM experiment_artifacts WHERE experiment_id = ?", (experiment.id,)
            )

            # Save metrics
            for metric in experiment.metrics:
                conn.execute(
                    """
                    INSERT INTO experiment_metrics (
                        experiment_id, name, value, metric_type, timestamp,
                        iteration, step, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        experiment.id,
                        metric.name,
                        json.dumps(metric.value),
                        metric.metric_type.value,
                        metric.timestamp.isoformat(),
                        metric.iteration,
                        metric.step,
                        json.dumps(metric.metadata),
                    ),
                )

            # Save artifacts
            for artifact in experiment.artifacts:
                conn.execute(
                    """
                    INSERT INTO experiment_artifacts (
                        id, experiment_id, name, artifact_type, file_path,
                        content, size_bytes, checksum, created_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        artifact.id,
                        experiment.id,
                        artifact.name,
                        artifact.artifact_type,
                        artifact.file_path,
                        artifact.content,
                        artifact.size_bytes,
                        artifact.checksum,
                        artifact.created_at.isoformat(),
                        json.dumps(artifact.metadata),
                    ),
                )

            conn.commit()
            logger.info(f"Saved experiment {experiment.id} to database")

        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving experiment {experiment.id}: {e}")
            raise ExperimentDatabaseError(f"Failed to save experiment: {e}")

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get an experiment by ID.

        Args:
            experiment_id: ID of the experiment to retrieve

        Returns:
            Experiment if found, None otherwise
        """
        conn = self._get_connection()

        # Get main experiment record
        row = conn.execute(
            """
            SELECT * FROM experiments WHERE id = ?
        """,
            (experiment_id,),
        ).fetchone()

        if not row:
            return None

        try:
            # Parse the experiment data
            experiment_data = {
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'status': row['status'],
                'created_at': datetime.fromisoformat(row['created_at']),
                'started_at': (
                    datetime.fromisoformat(row['started_at']) if row['started_at'] else None
                ),
                'completed_at': (
                    datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None
                ),
                'updated_at': datetime.fromisoformat(row['updated_at']),
                'config': ExperimentConfig.model_validate_json(row['config_json']),
                'result': (
                    ExperimentResult.model_validate_json(row['result_json'])
                    if row['result_json']
                    else None
                ),
                'git_commit': row['git_commit'],
                'git_branch': row['git_branch'],
                'git_repository': row['git_repository'],
                'code_version': row['code_version'],
                'parent_experiment_id': row['parent_experiment_id'],
                'created_by': row['created_by'],
                'tags': json.loads(row['tags_json']) if row['tags_json'] else [],
                'metadata': json.loads(row['metadata_json']) if row['metadata_json'] else {},
                'metrics': [],
                'artifacts': [],
            }

            # Get metrics
            metric_rows = conn.execute(
                """
                SELECT * FROM experiment_metrics WHERE experiment_id = ?
                ORDER BY timestamp
            """,
                (experiment_id,),
            ).fetchall()

            for metric_row in metric_rows:
                metric = ExperimentMetric(
                    name=metric_row['name'],
                    value=json.loads(metric_row['value']),
                    metric_type=MetricType(metric_row['metric_type']),
                    timestamp=datetime.fromisoformat(metric_row['timestamp']),
                    iteration=metric_row['iteration'],
                    step=metric_row['step'],
                    metadata=(
                        json.loads(metric_row['metadata_json'])
                        if metric_row['metadata_json']
                        else {}
                    ),
                )
                experiment_data['metrics'].append(metric)

            # Get artifacts
            artifact_rows = conn.execute(
                """
                SELECT * FROM experiment_artifacts WHERE experiment_id = ?
                ORDER BY created_at
            """,
                (experiment_id,),
            ).fetchall()

            for artifact_row in artifact_rows:
                from ..models.experiment import ExperimentArtifact

                artifact = ExperimentArtifact(
                    id=artifact_row['id'],
                    name=artifact_row['name'],
                    artifact_type=artifact_row['artifact_type'],
                    file_path=artifact_row['file_path'],
                    content=artifact_row['content'],
                    size_bytes=artifact_row['size_bytes'],
                    checksum=artifact_row['checksum'],
                    created_at=datetime.fromisoformat(artifact_row['created_at']),
                    metadata=(
                        json.loads(artifact_row['metadata_json'])
                        if artifact_row['metadata_json']
                        else {}
                    ),
                )
                experiment_data['artifacts'].append(artifact)

            return Experiment.model_validate(experiment_data)

        except Exception as e:
            logger.error(f"Error loading experiment {experiment_id}: {e}")
            raise ExperimentDatabaseError(f"Failed to load experiment: {e}")

    def list_experiments(
        self,
        status: Optional[ExperimentStatus] = None,
        experiment_type: Optional[ExperimentType] = None,
        created_by: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> List[Experiment]:
        """List experiments with optional filtering.

        Args:
            status: Filter by experiment status
            experiment_type: Filter by experiment type
            created_by: Filter by creator
            tags: Filter by tags (experiments must have all specified tags)
            limit: Maximum number of experiments to return
            offset: Number of experiments to skip
            order_by: Field to order by
            order_desc: Whether to order in descending order

        Returns:
            List of experiments matching the criteria
        """
        conn = self._get_connection()

        # Build query
        query = "SELECT id FROM experiments WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if experiment_type:
            query += " AND experiment_type = ?"
            params.append(experiment_type.value)

        if created_by:
            query += " AND created_by = ?"
            params.append(created_by)

        if tags:
            for tag in tags:
                query += " AND tags_json LIKE ?"
                params.append(f'%"{tag}"%')

        # Add ordering
        order_direction = "DESC" if order_desc else "ASC"
        query += f" ORDER BY {order_by} {order_direction}"

        # Add limit and offset
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        if offset:
            query += " OFFSET ?"
            params.append(offset)

        # Execute query and load experiments
        rows = conn.execute(query, params).fetchall()
        experiments = []

        for row in rows:
            experiment = self.get_experiment(row['id'])
            if experiment:
                experiments.append(experiment)

        return experiments

    def delete_experiment(self, experiment_id: str) -> bool:
        """Delete an experiment and all its data.

        Args:
            experiment_id: ID of the experiment to delete

        Returns:
            True if experiment was deleted, False if not found
        """
        conn = self._get_connection()

        try:
            cursor = conn.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Deleted experiment {experiment_id}")
                return True
            else:
                logger.warning(f"Experiment {experiment_id} not found for deletion")
                return False

        except Exception as e:
            conn.rollback()
            logger.error(f"Error deleting experiment {experiment_id}: {e}")
            raise ExperimentDatabaseError(f"Failed to delete experiment: {e}")

    def get_experiment_metrics(
        self, experiment_id: str, metric_name: Optional[str] = None
    ) -> List[ExperimentMetric]:
        """Get metrics for an experiment.

        Args:
            experiment_id: ID of the experiment
            metric_name: Optional specific metric name to filter by

        Returns:
            List of metrics
        """
        conn = self._get_connection()

        query = "SELECT * FROM experiment_metrics WHERE experiment_id = ?"
        params = [experiment_id]

        if metric_name:
            query += " AND name = ?"
            params.append(metric_name)

        query += " ORDER BY timestamp"

        rows = conn.execute(query, params).fetchall()
        metrics = []

        for row in rows:
            metric = ExperimentMetric(
                name=row['name'],
                value=json.loads(row['value']),
                metric_type=MetricType(row['metric_type']),
                timestamp=datetime.fromisoformat(row['timestamp']),
                iteration=row['iteration'],
                step=row['step'],
                metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {},
            )
            metrics.append(metric)

        return metrics

    def get_experiment_count(
        self,
        status: Optional[ExperimentStatus] = None,
        experiment_type: Optional[ExperimentType] = None,
        created_by: Optional[str] = None,
    ) -> int:
        """Get count of experiments matching criteria.

        Args:
            status: Filter by experiment status
            experiment_type: Filter by experiment type
            created_by: Filter by creator

        Returns:
            Number of experiments matching the criteria
        """
        conn = self._get_connection()

        query = "SELECT COUNT(*) as count FROM experiments WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if experiment_type:
            query += " AND experiment_type = ?"
            params.append(experiment_type.value)

        if created_by:
            query += " AND created_by = ?"
            params.append(created_by)

        row = conn.execute(query, params).fetchone()
        return row['count'] if row else 0

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> 'ExperimentDatabase':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


def create_experiment_database(db_path: Union[str, Path] = ":memory:") -> ExperimentDatabase:
    """Create and initialize an experiment database.

    Args:
        db_path: Path to the database file

    Returns:
        Initialized ExperimentDatabase instance
    """
    return ExperimentDatabase(db_path)
