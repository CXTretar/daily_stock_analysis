import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_alphasift_screen


def _empty_volume_breakout_result() -> dict:
    return {
        "strategy": "volume_breakout",
        "market": "cn",
        "snapshot_source": "sina",
        "snapshot_count": 5517,
        "after_filter_count": 0,
        "candidate_count": 0,
        "warnings": ["No candidates after daily hard filter"],
        "source_errors": [],
        "daily_enriched": True,
        "daily_enrich_count": 100,
        "candidates": [],
    }


def _dual_low_result() -> dict:
    return {
        "strategy": "dual_low",
        "market": "cn",
        "snapshot_source": "sina",
        "snapshot_count": 5517,
        "after_filter_count": 8,
        "candidate_count": 1,
        "warnings": [],
        "source_errors": [],
        "candidates": [{"code": "600519", "name": "贵州茅台"}],
    }


class RunAlphaSiftScreenTestCase(unittest.TestCase):
    def test_empty_candidates_write_json_before_returning_error(self) -> None:
        result = {
            "strategy": "volume_breakout",
            "market": "cn",
            "snapshot_source": "em_datacenter",
            "snapshot_count": 5196,
            "after_filter_count": 0,
            "candidate_count": 0,
            "warnings": ["No candidates after daily hard filter"],
            "source_errors": ["Snapshot source efinance failed"],
            "candidates": [],
        }

        class FakeConfig:
            alphasift_enabled = False

        class FakeAlphaSiftService:
            def __init__(self, *, config):
                self.config = config

            def screen(self, *, strategy, market, max_results):
                return result

        config_module = types.ModuleType("src.config")
        config_module.get_config = lambda: FakeConfig()
        service_module = types.ModuleType("src.services.alphasift_service")
        service_module.AlphaSiftService = FakeAlphaSiftService

        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "selection.json"
            argv = [
                "run_alphasift_screen.py",
                "--strategy",
                "volume_breakout",
                "--market",
                "cn",
                "--max-results",
                "3",
                "--output-json",
                str(output_json),
                "--fallback-strategies",
                "none",
            ]
            with patch.dict(
                sys.modules,
                {
                    "src.config": config_module,
                    "src.services.alphasift_service": service_module,
                },
            ), patch.object(sys, "argv", argv), self.assertLogs(level="ERROR") as logs:
                exit_code = run_alphasift_screen.main()

            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(output_json.read_text(encoding="utf-8")), result)
            self.assertIn("No candidates after daily hard filter", "\n".join(logs.output))
            self.assertIn("em_datacenter", "\n".join(logs.output))

    def test_empty_primary_uses_fallback_strategy(self) -> None:
        primary_result = _empty_volume_breakout_result()
        fallback_result = _dual_low_result()
        calls = []

        class FakeConfig:
            alphasift_enabled = False

        class FakeAlphaSiftService:
            def __init__(self, *, config):
                self.config = config

            def screen(self, *, strategy, market, max_results):
                calls.append((strategy, market, max_results))
                return primary_result if strategy == "volume_breakout" else fallback_result

        config_module = types.ModuleType("src.config")
        config_module.get_config = lambda: FakeConfig()
        service_module = types.ModuleType("src.services.alphasift_service")
        service_module.AlphaSiftService = FakeAlphaSiftService

        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "selection.json"
            argv = [
                "run_alphasift_screen.py",
                "--strategy",
                "volume_breakout",
                "--market",
                "cn",
                "--max-results",
                "3",
                "--output-json",
                str(output_json),
                "--fallback-strategies",
                "dual_low",
            ]
            stdout = io.StringIO()
            with patch.dict(
                sys.modules,
                {
                    "src.config": config_module,
                    "src.services.alphasift_service": service_module,
                },
            ), patch.object(sys, "argv", argv), self.assertLogs(level="WARNING") as logs:
                with contextlib.redirect_stdout(stdout):
                    exit_code = run_alphasift_screen.main()

            payload = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue().strip(), "600519")
        self.assertEqual(calls, [("volume_breakout", "cn", 3), ("dual_low", "cn", 3)])
        self.assertEqual(payload["strategy"], "dual_low")
        self.assertEqual(payload["warnings"][-1], (
            "Primary strategy volume_breakout returned no usable stock codes; "
            "fallback strategy dual_low selected."
        ))
        self.assertEqual(
            payload["selection_fallback"],
            {
                "trigger": "empty_primary_result",
                "primary_strategy": "volume_breakout",
                "fallback_strategy": "dual_low",
                "attempted_strategies": ["volume_breakout", "dual_low"],
                "primary_diagnostics": {
                    "strategy": "volume_breakout",
                    "market": "cn",
                    "snapshot_source": "sina",
                    "snapshot_count": 5517,
                    "after_filter_count": 0,
                    "candidate_count": 0,
                    "warnings": ["No candidates after daily hard filter"],
                    "source_errors": [],
                    "daily_enriched": True,
                    "daily_enrich_count": 100,
                },
            },
        )
        self.assertIn("trying fallback strategy dual_low", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
