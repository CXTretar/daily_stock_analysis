import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_alphasift_screen


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


if __name__ == "__main__":
    unittest.main()
