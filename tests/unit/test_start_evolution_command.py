"""Tests for the evoseal start evolution command.

Verifies that the command prints the research-stage notice, constructs
the ContinuousEvolutionService with the right arguments, and invokes
asyncio.run(service.start()) — without actually running the daemon.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from evoseal.cli.main import app

runner = CliRunner()

pytestmark = pytest.mark.unit


class TestStartEvolutionCommand:
    """Test suite for the start evolution command."""

    @patch(
        "evoseal.services.continuous_evolution_service.ContinuousEvolutionService",
    )
    @patch("evoseal.cli.commands.start.asyncio.run")
    def test_start_evolution_runs_service(self, mock_run, mock_service_cls):
        """Constructs the service and calls asyncio.run(service.start())."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

        result = runner.invoke(app, ["start", "evolution"])

        assert result.exit_code == 0
        # Research-stage notice appears
        assert "Research-stage" in result.output
        assert "NOT yet closed" in result.output
        # Service constructed with defaults
        mock_service_cls.assert_called_once_with(
            data_dir=None,
            evolution_interval=3600,
            training_check_interval=1800,
        )
        # asyncio.run invoked with service.start()
        mock_run.assert_called_once()
        mock_run.assert_called_with(mock_service.start())

    @patch(
        "evoseal.services.continuous_evolution_service.ContinuousEvolutionService",
    )
    @patch("evoseal.cli.commands.start.asyncio.run")
    def test_start_evolution_custom_options(self, mock_run, mock_service_cls):
        """Custom options are forwarded to the service constructor."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "start",
                "evolution",
                "--data-dir",
                "/tmp/evo_data",
                "--evolution-interval",
                "7200",
                "--training-check-interval",
                "900",
            ],
        )

        assert result.exit_code == 0
        mock_service_cls.assert_called_once_with(
            data_dir=Path("/tmp/evo_data"),
            evolution_interval=7200,
            training_check_interval=900,
        )

    @patch(
        "evoseal.services.continuous_evolution_service.ContinuousEvolutionService",
    )
    @patch("evoseal.cli.commands.start.asyncio.run", side_effect=KeyboardInterrupt)
    def test_start_evolution_keyboard_interrupt(self, mock_run, mock_service_cls):
        """KeyboardInterrupt produces a clean 'Stopped.' message and exits 0."""
        mock_service_cls.return_value = MagicMock()

        result = runner.invoke(app, ["start", "evolution"])

        assert result.exit_code == 0
        assert "Stopped." in result.output

    @patch(
        "evoseal.services.continuous_evolution_service.ContinuousEvolutionService",
    )
    @patch(
        "evoseal.cli.commands.start.asyncio.run",
        side_effect=RuntimeError("bad config"),
    )
    def test_start_evolution_runtime_error(self, mock_run, mock_service_cls):
        """Runtime errors produce a clean CLI message, not a raw traceback."""
        mock_service_cls.return_value = MagicMock()

        result = runner.invoke(app, ["start", "evolution"])

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "bad config" in result.output
