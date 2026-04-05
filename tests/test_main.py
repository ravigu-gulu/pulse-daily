"""Tests for main.py module logic."""
import json
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestDoReportOnly:
    def _write_snap(self, snap_dir, name, data):
        (snap_dir / f"{name}_raw.json").write_text(json.dumps(data.get("raw", {})))
        (snap_dir / f"{name}_claude.json").write_text(json.dumps(data.get("claude", {})))
        (snap_dir / f"{name}_gpt.json").write_text(json.dumps(data.get("gpt", {})))

    def test_loads_valid_snapshots(self):
        from main import do_report_only
        from datetime import date

        with tempfile.TemporaryDirectory() as tmpdir:
            snap_dir = Path(tmpdir) / "2026-04-05"
            snap_dir.mkdir()
            for mod in ["finance", "news", "ai", "github"]:
                self._write_snap(snap_dir, mod, {
                    "raw": {"key": "val"},
                    "claude": {"result": "ok"},
                    "gpt": {"result": "ok"},
                })

            import main as m
            orig = m.SNAPSHOTS_DIR
            m.SNAPSHOTS_DIR = Path(tmpdir)
            try:
                results = do_report_only(date(2026, 4, 5))
            finally:
                m.SNAPSHOTS_DIR = orig

        assert "finance" in results
        assert results["finance"]["claude"] == {"result": "ok"}

    def test_missing_snap_returns_error_dict(self):
        from main import do_report_only
        from datetime import date

        with tempfile.TemporaryDirectory() as tmpdir:
            snap_dir = Path(tmpdir) / "2026-04-05"
            snap_dir.mkdir()
            # Only write finance, others missing
            (snap_dir / "finance_raw.json").write_text("{}")
            (snap_dir / "finance_claude.json").write_text('{"ok": true}')
            (snap_dir / "finance_gpt.json").write_text('{"ok": true}')

            import main as m
            orig = m.SNAPSHOTS_DIR
            m.SNAPSHOTS_DIR = Path(tmpdir)
            try:
                results = do_report_only(date(2026, 4, 5))
            finally:
                m.SNAPSHOTS_DIR = orig

        # missing files return fallback, not crash
        assert results["news"]["claude"] == {"error": "无快照"}

    def test_corrupted_snap_returns_error_dict(self):
        from main import do_report_only
        from datetime import date

        with tempfile.TemporaryDirectory() as tmpdir:
            snap_dir = Path(tmpdir) / "2026-04-05"
            snap_dir.mkdir()
            for mod in ["finance", "news", "ai", "github"]:
                (snap_dir / f"{mod}_raw.json").write_text("{}")
                (snap_dir / f"{mod}_claude.json").write_text("NOT VALID JSON {{{{")
                (snap_dir / f"{mod}_gpt.json").write_text("{}")

            import main as m
            orig = m.SNAPSHOTS_DIR
            m.SNAPSHOTS_DIR = Path(tmpdir)
            try:
                results = do_report_only(date(2026, 4, 5))
            finally:
                m.SNAPSHOTS_DIR = orig

        # corrupted JSON should return error dict, not raise
        assert results["finance"]["claude"].get("error") == "快照损坏"

    def test_no_snapshot_dir_exits(self):
        from main import do_report_only
        from datetime import date
        import pytest

        with tempfile.TemporaryDirectory() as tmpdir:
            import main as m
            orig = m.SNAPSHOTS_DIR
            m.SNAPSHOTS_DIR = Path(tmpdir)
            try:
                with pytest.raises(SystemExit):
                    do_report_only(date(2099, 1, 1))  # no snapshot for this date
            finally:
                m.SNAPSHOTS_DIR = orig


class TestRunModule:
    def test_fetch_failure_returns_error_dict(self):
        from main import run_module
        from pathlib import Path
        import tempfile

        def bad_fetch():
            raise RuntimeError("网络故障")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_module("test", bad_fetch, Path(tmpdir))

        assert "error" in result["claude"]
        assert "error" in result["gpt"]

    def test_success_returns_raw_and_analysis(self):
        from main import run_module
        from unittest.mock import patch
        import tempfile

        def good_fetch():
            return {"items": [1, 2, 3]}

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch('main.analyze', return_value={"claude": {"ok": True}, "gpt": {"ok": True}}):
            result = run_module("test", good_fetch, Path(tmpdir))

        assert result["raw"] == {"items": [1, 2, 3]}
        assert result["claude"] == {"ok": True}
