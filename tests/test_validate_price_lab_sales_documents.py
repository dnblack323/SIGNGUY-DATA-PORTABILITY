from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from validate_price_lab_sales_documents import ValidationError, content_hash, validate_json_schema, validate_package


def load_fixture(name: str = "price-lab-sales-documents-v1-sample.json") -> dict:
    return json.loads((ROOT / "fixtures" / "golden" / name).read_text(encoding="utf-8"))


class PriceLabSalesDocumentPackageValidationTests(unittest.TestCase):
    def assert_invalid(self, package: dict, pattern: str):
        with self.assertRaisesRegex(ValidationError, pattern):
            validate_package(package)

    def test_sample_package_is_valid_and_hash_is_deterministic(self):
        package = load_fixture()
        self.assertEqual(validate_package(package), ["json schema valid", "semantic sales document package valid"])
        self.assertEqual(package["manifest"]["contentSha256"], content_hash(package))

    def test_schema_rejects_unsupported_version(self):
        package = load_fixture()
        package["manifest"]["formatVersion"] = 999
        with self.assertRaisesRegex(ValidationError, "schema validation failed"):
            validate_json_schema(package)

    def test_manifest_hash_tampering_is_rejected(self):
        package = load_fixture()
        package["documents"][0]["title"] = "Tampered"
        self.assert_invalid(package, "contentSha256 mismatch")

    def test_manifest_record_counts_are_enforced(self):
        package = load_fixture()
        package["manifest"]["recordCounts"]["documents"] = 99
        self.assert_invalid(package, "recordCounts.documents mismatch|contentSha256 mismatch")

    def test_duplicate_portable_ids_are_rejected(self):
        package = load_fixture()
        duplicate = copy.deepcopy(package["documents"][0])
        package["documents"].append(duplicate)
        package["manifest"]["recordCounts"]["documents"] += 1
        package["manifest"]["contentSha256"] = content_hash(package)
        self.assert_invalid(package, "duplicate portableId")

    def test_missing_conversion_ancestry_is_rejected(self):
        package = load_fixture()
        package["documents"][1]["sourceDocumentPortableId"] = "plsd_v1_document_000000000000"
        package["manifest"]["contentSha256"] = content_hash(package)
        self.assert_invalid(package, "source ancestry is missing")

    def test_conflicting_current_revision_is_rejected(self):
        package = load_fixture()
        package["documents"][0]["currentRevisionPortableId"] = package["revisions"][1]["portableId"]
        package["manifest"]["contentSha256"] = content_hash(package)
        self.assert_invalid(package, "belongs to another document")

    def test_malicious_asset_or_pdf_paths_are_rejected(self):
        package = load_fixture()
        package["pdfOutputs"][0]["filename"] = "../invoice.pdf"
        with self.assertRaisesRegex(ValidationError, "schema validation failed"):
            validate_package(package)

    def test_logo_asset_hash_and_size_are_enforced(self):
        package = load_fixture()
        package["assets"][0]["sizeBytes"] = 999
        package["manifest"]["contentSha256"] = content_hash(package)
        self.assert_invalid(package, "asset sizeBytes mismatch")

    def test_forbidden_secret_or_machine_keys_are_rejected(self):
        package = load_fixture()
        package["customers"][0]["contact"]["api_token"] = "not allowed"
        package["manifest"]["contentSha256"] = content_hash(package)
        self.assert_invalid(package, "forbidden secret")

        package = load_fixture()
        package["documents"][0]["localPath"] = "C:\\Users\\Example\\Documents\\leak.json"
        package["manifest"]["contentSha256"] = content_hash(package)
        self.assert_invalid(package, "Additional properties|forbidden secret")

    def test_customer_projection_and_revision_evidence_are_required(self):
        package = load_fixture()
        package["revisions"][0]["sourceEvidence"].pop("showTheMath")
        package["manifest"]["contentSha256"] = content_hash(package)
        self.assert_invalid(package, "Show the Math")

        package = load_fixture()
        package["customerProjections"][0]["projection"]["view"] = "internal"
        package["manifest"]["contentSha256"] = content_hash(package)
        self.assert_invalid(package, "customer-safe view marker")


if __name__ == "__main__":
    unittest.main()
