from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from validate_portable_package import ValidationError, validate_json_schema, validate_package


def load_fixture(name: str = "v1-sample-package.json") -> dict:
    return json.loads((ROOT / "fixtures" / "golden" / name).read_text(encoding="utf-8"))


class PortablePackageValidationTests(unittest.TestCase):
    def assert_invalid(self, package: dict, pattern: str):
        with self.assertRaisesRegex(ValidationError, pattern):
            validate_package(package)

    def test_empty_golden_package_is_valid(self):
        self.assertEqual(validate_package(load_fixture("v1-empty-package.json")), ["json schema valid", "semantic package valid"])

    def test_sample_golden_package_is_valid(self):
        self.assertEqual(validate_package(load_fixture()), ["json schema valid", "semantic package valid"])

    def test_schema_validation_uses_format_checker(self):
        package = load_fixture()
        package["orders"][0]["document_date"] = "not-a-date"
        with self.assertRaisesRegex(ValidationError, "schema validation failed"):
            validate_json_schema(package)

    def test_estimate_line_item_preservation_is_required(self):
        package = load_fixture()
        package["estimate_items"] = []
        package["manifest"]["entity_counts"]["estimate_items"] = 0
        package["order_items"][0]["source_estimate_item_portable_id"] = None
        self.assert_invalid(package, "estimate subtotal_cents does not match estimate items")

    def test_work_order_relationships_are_validated(self):
        package = load_fixture()
        package["work_orders"][0]["items_snapshot"][0]["order_item_portable_id"] = "sgp_v1_order_item_00000000-0000-4000-8000-000000009999"
        self.assert_invalid(package, "work order item snapshot references wrong source type")

    def test_assignment_references_must_be_safe_user_refs(self):
        package = load_fixture()
        package["order_items"][0]["assigned_user_portable_id"] = package["customers"][0]["portable_id"]
        self.assert_invalid(package, "assigned_user_portable_id references wrong source type")

    def test_same_tenant_rejection(self):
        package = load_fixture()
        other_tenant = {
            "portable_id": "sgp_v1_tenant_00000000-0000-4000-8000-000000000999",
            "name": "Other Tenant",
            "timezone": "America/New_York",
            "locale": "en-US",
            "currency": "USD",
            "sales_tax_rate_basis_points": 0,
        }
        package["tenants"].append(other_tenant)
        package["manifest"]["entity_counts"]["tenants"] = 2
        package["customers"][0]["tenant_portable_id"] = other_tenant["portable_id"]
        self.assert_invalid(package, "crosses tenant boundary")

    def test_wrong_source_type_rejection(self):
        package = load_fixture()
        package["notes"][0]["source_type"] = "customer"
        package["notes"][0]["source_portable_id"] = package["orders"][0]["portable_id"]
        self.assert_invalid(package, "references wrong source type")

    def test_duplicate_ids_are_rejected(self):
        package = load_fixture()
        duplicate = copy.deepcopy(package["users"][0])
        package["users"].append(duplicate)
        package["manifest"]["entity_counts"]["users"] = 2
        self.assert_invalid(package, "duplicate portable_id")

    def test_invalid_totals_are_rejected(self):
        package = load_fixture()
        package["invoices"][0]["balance_due_cents"] = 1
        self.assert_invalid(package, "invoice balance_due_cents invariant failed")

    def test_forbidden_secrets_are_rejected(self):
        package = load_fixture()
        package["users"][0]["password_hash"] = "not allowed"
        with self.assertRaisesRegex(ValidationError, "schema validation failed|forbidden secret-like key"):
            validate_package(package)

    def test_malformed_dates_are_rejected(self):
        package = load_fixture()
        package["calendar_events"][0]["start_at"] = "2026-99-99T99:99:99Z"
        self.assert_invalid(package, "malformed date-time")

    def test_missing_manifest_counts_are_rejected(self):
        package = load_fixture()
        del package["manifest"]["entity_counts"]["work_orders"]
        self.assert_invalid(package, "schema validation failed")

    def test_file_inventory_checksum_mismatches_are_rejected(self):
        package = load_fixture()
        package["manifest"]["file_inventory"][0]["sha256"] = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        self.assert_invalid(package, "file inventory sha256 mismatch")

    def test_calendar_completion_remains_separate_from_production_completion(self):
        package = load_fixture()
        package["calendar_events"][0]["status"] = "complete"
        package["calendar_events"][0]["completion_affects_production"] = True
        self.assert_invalid(package, "schema validation failed")

    def test_malformed_fixture_rejection(self):
        package = json.loads((ROOT / "fixtures" / "invalid" / "v1-invalid-file-inventory.json").read_text(encoding="utf-8"))
        self.assert_invalid(package, "file_inventory count mismatch|references wrong source type")


if __name__ == "__main__":
    unittest.main()
