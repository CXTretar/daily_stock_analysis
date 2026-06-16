#!/usr/bin/env python3
"""Run AlphaSift screening and print selected stock codes.

This script is intentionally small: it reuses DSA's existing AlphaSift service
instead of duplicating screening logic, then emits a comma-separated stock list
that can be exported as STOCK_LIST for the normal analysis pipeline.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _parse_bool(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logging.warning("Invalid %s=%r, falling back to %s.", name, raw, default)
        return default


def _candidate_code(candidate: Dict[str, Any]) -> str:
    return str(
        candidate.get("code")
        or candidate.get("stock_code")
        or candidate.get("symbol")
        or ""
    ).strip()


def _selected_codes(candidates: Iterable[Dict[str, Any]]) -> List[str]:
    codes: List[str] = []
    seen = set()
    for candidate in candidates:
        code = _candidate_code(candidate)
        if not code:
            continue
        normalized = code.upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        codes.append(code)
    return codes


def _write_github_env(name: str, value: str) -> None:
    github_env = os.getenv("GITHUB_ENV")
    if not github_env:
        return
    with open(github_env, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AlphaSift stock screening.")
    parser.add_argument(
        "--strategy",
        default=os.getenv("STOCK_SELECTION_STRATEGY", "dual_low"),
        help="AlphaSift strategy id.",
    )
    parser.add_argument(
        "--market",
        default=os.getenv("STOCK_SELECTION_MARKET", "cn"),
        help="Market scope supported by AlphaSift, currently cn.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=_env_int("STOCK_SELECTION_MAX_RESULTS", 3),
        help="Maximum selected candidates to analyze.",
    )
    parser.add_argument(
        "--output-json",
        default=os.getenv("STOCK_SELECTION_OUTPUT_JSON", ""),
        help="Optional path to save the full screening result.",
    )
    parser.add_argument(
        "--write-github-env",
        action="store_true",
        default=_parse_bool(os.getenv("STOCK_SELECTION_WRITE_GITHUB_ENV", "false")),
        help="Append STOCK_LIST and STOCK_SELECTION_RESULT_JSON to GITHUB_ENV.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.max_results < 1:
        parser.error("--max-results must be >= 1")

    from src.config import get_config
    from src.services.alphasift_service import AlphaSiftService

    config = get_config()
    if not config.alphasift_enabled:
        logging.info("ALPHASIFT_ENABLED is false; enabling it for this screening run.")
        config.alphasift_enabled = True

    result = AlphaSiftService(config=config).screen(
        strategy=args.strategy,
        market=args.market,
        max_results=args.max_results,
    )
    candidates = result.get("candidates") if isinstance(result, dict) else []
    codes = _selected_codes(candidates if isinstance(candidates, list) else [])
    if not codes:
        logging.error("AlphaSift screening returned no usable stock codes.")
        return 2

    stock_list = ",".join(codes)
    print(stock_list)

    output_json = args.output_json.strip()
    if output_json:
        output_path = Path(output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.write_github_env:
        _write_github_env("STOCK_LIST", stock_list)
        if output_json:
            _write_github_env("STOCK_SELECTION_RESULT_JSON", output_json)

    logging.info(
        "AlphaSift selected %d stock(s): %s",
        len(codes),
        stock_list,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
