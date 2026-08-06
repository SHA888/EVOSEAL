"""Tests for pipeline logs --follow implementation."""

from __future__ import annotations

import os
import time
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from evoseal.cli.commands.pipeline import _print_log_line, app, follow_logs

runner = CliRunner()


class TestPrintLogLine:
    """Tests for the _print_log_line helper."""

    def test_error_line_printed_red(self, capsys):
        _print_log_line("2026-08-05 ERROR something broke\n")
        captured = capsys.readouterr()
        assert "something broke" in captured.out

    def test_warning_line_printed(self, capsys):
        _print_log_line("2026-08-05 WARNING low memory\n")
        captured = capsys.readouterr()
        assert "low memory" in captured.out

    def test_info_line_printed(self, capsys):
        _print_log_line("2026-08-05 INFO pipeline started\n")
        captured = capsys.readouterr()
        assert "pipeline started" in captured.out

    def test_debug_line_printed(self, capsys):
        _print_log_line("2026-08-05 DEBUG verbose output\n")
        captured = capsys.readouterr()
        assert "verbose output" in captured.out

    def test_plain_line_printed(self, capsys):
        _print_log_line("no level here\n")
        captured = capsys.readouterr()
        assert "no level here" in captured.out


class TestFollowLogs:
    """Tests for the follow_logs function."""

    def test_exits_when_file_missing(self, tmp_path):
        missing = str(tmp_path / "no_such_file.log")
        with pytest.raises(typer.Exit):
            follow_logs(missing)

    def test_shows_initial_lines(self, tmp_path, capsys):
        log_file = str(tmp_path / "pipeline.log")
        with open(log_file, "w") as f:
            for i in range(10):
                f.write(f"INFO line {i}\n")

        # follow_logs will loop forever, so interrupt it immediately
        with patch("evoseal.cli.commands.pipeline.time") as mock_time:
            mock_time.sleep.side_effect = KeyboardInterrupt
            follow_logs(log_file, initial_lines=5, level=None)

        captured = capsys.readouterr()
        # Should show last 5 lines (lines 5-9)
        assert "line 5" in captured.out
        assert "line 9" in captured.out
        # Should not show first 5 lines
        assert "line 0" not in captured.out

    def test_filters_by_level(self, tmp_path, capsys):
        log_file = str(tmp_path / "pipeline.log")
        with open(log_file, "w") as f:
            f.write("INFO starting\n")
            f.write("ERROR something broke\n")
            f.write("INFO still running\n")
            f.write("WARNING low memory\n")

        with patch("evoseal.cli.commands.pipeline.time") as mock_time:
            mock_time.sleep.side_effect = KeyboardInterrupt
            follow_logs(log_file, initial_lines=10, level="ERROR")

        captured = capsys.readouterr()
        assert "something broke" in captured.out
        # INFO and WARNING lines should be filtered out
        assert "starting" not in captured.out
        assert "still running" not in captured.out
        assert "low memory" not in captured.out

    def test_follows_new_lines(self, tmp_path, capsys):
        log_file = str(tmp_path / "pipeline.log")
        with open(log_file, "w") as f:
            f.write("INFO initial line\n")

        call_count = 0

        def mock_sleep_with_write(_seconds):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Append a new line during the first sleep
                with open(log_file, "a") as f:
                    f.write("ERROR new error appeared\n")
            else:
                raise KeyboardInterrupt

        with patch("evoseal.cli.commands.pipeline.time.sleep", side_effect=mock_sleep_with_write):
            follow_logs(log_file, initial_lines=5, level=None)

        captured = capsys.readouterr()
        assert "initial line" in captured.out
        assert "new error appeared" in captured.out


class TestShowLogsFollowFlag:
    """Integration test for the --follow flag on the logs command."""

    def test_follow_flag_calls_follow_logs(self, tmp_path):
        log_file = str(tmp_path / "pipeline.log")
        with open(log_file, "w") as f:
            f.write("INFO test\n")

        with (
            patch("evoseal.cli.commands.pipeline.PIPELINE_LOG_FILE", log_file),
            patch("evoseal.cli.commands.pipeline.follow_logs") as mock_follow,
        ):
            result = runner.invoke(app, ["logs", "--follow"])
            mock_follow.assert_called_once_with(log_file, 50, None)
