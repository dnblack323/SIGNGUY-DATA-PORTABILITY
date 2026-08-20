from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from validate_portable_package import ValidationError, validate_package


def load_fixture() -> dict:
    return json.loads((ROOT / "fixtures" / "golden" / "v1-empty-package.json").read_text(encoding="utf-8"))


class PortablePackageValidationTests(unittest.TestCase):
    def test_empty_golden_package_is_valid(self):
        self.assertEqual(validate_package(load_fixture()), ["package valid"])

    def test_rejects_secret_like_keys(self):
        package = load_fixture()
        package["manifest"]["api_key"] = "not allowed"
        with self.assertRaisesRegex(ValidationError, "forbidden secret-like key"):
            validate_package(package)

    def test_rejects_non_empty_unknown_top_level_section(self):
        package = load_fixture()
        package["messages"] = []
        with self.assertRaisesRegex(ValidationError, "top-level sections mismatch"):
            validate_package(package)

    def test_rejects_calendar_completion_that_mutates_production(self):
        package = load_fixture()
        tenant_id = package["tenants"][0]["portable_id"]
        package["calendar_events"].append(
            {
                "portable_id": "sgp_v1_calendar_event_00000000-0000-4000-8000-000000000020",
                "tenant_portable_id": tenant_id,
                "order_portable_id": None,
                "order_item_portable_id": None,
                "title": "Install",
                "status": "complete",
                "start_at": "2026-08-20T13:00:00Z",
                "end_at": None,
                "all_day": False,
                "assigned_user_portable_id": None,
                "note": None,
                "completion_affects_production": True,
            }
        )
        with self.assertRaisesRegex(ValidationError, "calendar completion"):
            validate_package(package)

    def test_rejects_duplicate_portable_id(self):
        package = load_fixture()
        duplicate = copy.deepcopy(package["tenants"][0])
        package["tenants"].append(duplicate)
        with self.assertRaisesRegex(ValidationError, "duplicate_portable_id|duplicate portable_id"):
            validate_package(package)


if __name__ == "__main__":
    unittest.main()
