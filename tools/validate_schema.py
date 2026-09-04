from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATHS = (
    ROOT / "schemas" / "signguy-slim-portable-v1.schema.json",
    ROOT / "schemas" / "price-lab-sales-documents-v1.schema.json",
)


def main() -> int:
    for schema_path in SCHEMA_PATHS:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    print("schema valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
