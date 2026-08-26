from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "signguy-pricing-profile-v1.schema.json"

FORBIDDEN_KEYS = {
    "customer",
    "estimate",
    "order",
    "invoice",
    "payment",
    "credential",
    "license",
    "token",
    "secret",
    "password",
    "private_url",
    "sqlite",
    "database_path",
}


class ValidationError(ValueError):
    pass


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key, child
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_json_schema(profile: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(_load_schema(), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(profile), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = "$" + "".join(f"[{part!r}]" if isinstance(part, int) else f".{part}" for part in first.path)
        raise ValidationError(f"schema validation failed at {location}: {first.message}")
    return ["json schema valid"]


def validate_no_excluded_data(profile: dict[str, Any]) -> list[str]:
    for path, key, child in _walk(profile):
        lowered = key.lower()
        _require(not any(forbidden in lowered for forbidden in FORBIDDEN_KEYS), f"forbidden excluded key {key!r} at {path}")
        if isinstance(child, str):
            _require(not re.search(r"([A-Za-z]:\\|\\\\|/Users/|\\Users\\|sqlite|license|token|secret|password)", child, re.I), f"forbidden private value at {path}.{key}")
    return ["excluded data absent"]


def validate_semantics(profile: dict[str, Any]) -> list[str]:
    entries = profile["pricing_entries"]
    _require(profile["manifest"]["entry_count"] == len(entries), "manifest entry_count mismatch")
    seen = set()
    for entry in entries:
        identity = (entry["stable_key"], entry["source_class"], entry["provenance"].get("pack_version", ""))
        _require(identity not in seen, f"duplicate pricing entry identity: {entry['stable_key']}")
        seen.add(identity)
        provenance = entry["provenance"]
        if entry["source_class"] in {"starter", "benchmark"}:
            _require(provenance.get("pack_type") == entry["source_class"], "pack_type must match packed source_class")
            _require(bool(provenance.get("pack_version")), "packed source requires pack_version")
        else:
            _require("pack_version" not in provenance and "pack_type" not in provenance, "shop/fallback/demo values must not claim a pack")
    return ["pricing profile semantics valid"]


def validate_pricing_profile(profile: dict[str, Any]) -> list[str]:
    checks: list[str] = []
    checks.extend(validate_json_schema(profile))
    checks.extend(validate_no_excluded_data(profile))
    checks.extend(validate_semantics(profile))
    return checks


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_pricing_profile.py <pricing-profile.json>", file=sys.stderr)
        return 2
    profile = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    try:
        for check in validate_pricing_profile(profile):
            print(check)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
