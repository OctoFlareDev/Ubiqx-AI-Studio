#!/usr/bin/env python3
"""Regenerate the committed OpenAPI contract from the FastAPI implementation.

Run from the repository root with the backend environment active:

    python scripts/generate_contract.py

The output is deterministic (sorted keys) so contract tests can compare the
running app against this committed file byte-for-byte after parsing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
CONTRACT_PATH = ROOT / "packages" / "contracts" / "openapi.json"

sys.path.insert(0, str(API_DIR))

from app.main import app  # noqa: E402


def main() -> None:
    schema = app.openapi()
    payload = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    CONTRACT_PATH.write_text(payload, encoding="utf-8")
    print(f"Wrote {CONTRACT_PATH} ({len(payload)} bytes)")


if __name__ == "__main__":
    main()
