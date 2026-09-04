from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from validate_price_lab_sales_documents import ValidationError, _load_package, content_hash, validate_json_schema, validate_package


def load_fixture(name: str = "price-lab-sales-documents-v1-sample.json") -> dict:
    return json.loads((ROOT / "fixtures" / "golden" / name).read_text(encoding="utf-8"))


def refresh_hash(package: dict) -> dict:
    package["manifest"]["recordCounts"] = {
        "customers": len(package["customers"]),
        "projects": len(package["projects"]),
        "documents": len(package["documents"]),
        "revisions": len(package["revisions"]),
        "customerProjections": len(package["customerProjections"]),
        "brandingProfiles": len(package["brandingProfiles"]),
        "templates": len(package["templates"]),
        "pdfOutputs": len(package["pdfOutputs"]),
        "assets": len(package["assets"]),
    }
    package["manifest"]["contentSha256"] = content_hash(package)
    return package


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
        refresh_hash(package)
        self.assert_invalid(package, "source ancestry is missing")

    def test_conversion_root_must_match_source_chain(self):
        package = load_fixture()
        package["documents"][1]["rootDocumentPortableId"] = package["documents"][1]["portableId"]
        refresh_hash(package)
        self.assert_invalid(package, "root ancestry does not match source chain")

    def test_conflicting_current_revision_is_rejected(self):
        package = load_fixture()
        package["documents"][0]["currentRevisionPortableId"] = package["revisions"][1]["portableId"]
        refresh_hash(package)
        self.assert_invalid(package, "belongs to another document")

    def test_finalized_documents_must_identify_current_revision(self):
        package = load_fixture()
        package["documents"][0]["currentRevisionPortableId"] = None
        refresh_hash(package)
        self.assert_invalid(package, "finalized document must identify a current revision")

    def test_project_and_document_customer_references_must_match(self):
        package = load_fixture()
        other_customer = copy.deepcopy(package["customers"][0])
        other_customer["portableId"] = "plsd_v1_customer_aaaaaaaaaaaa"
        other_customer["sourceLocalId"] = "customer-other"
        package["customers"].append(other_customer)
        package["projects"][0]["customerPortableId"] = other_customer["portableId"]
        refresh_hash(package)
        self.assert_invalid(package, "customer references do not agree")

    def test_duplicate_revision_numbers_within_document_are_rejected(self):
        package = load_fixture()
        duplicate = copy.deepcopy(package["revisions"][0])
        duplicate["portableId"] = "plsd_v1_revision_aaaaaaaaaaaa"
        duplicate["sourceLocalId"] = "revision-duplicate"
        package["revisions"].append(duplicate)
        refresh_hash(package)
        self.assert_invalid(package, "duplicate revision number")

    def test_projection_revision_must_belong_to_projection_document(self):
        package = load_fixture()
        package["customerProjections"][0]["revisionPortableId"] = package["revisions"][1]["portableId"]
        refresh_hash(package)
        self.assert_invalid(package, "projection revision belongs to another document")

    def test_malicious_asset_or_pdf_paths_are_rejected(self):
        package = load_fixture()
        package["pdfOutputs"][0]["filename"] = "../invoice.pdf"
        with self.assertRaisesRegex(ValidationError, "schema validation failed"):
            validate_package(package)

    def test_logo_asset_hash_and_size_are_enforced(self):
        package = load_fixture()
        package["assets"][0]["sizeBytes"] = 999
        refresh_hash(package)
        self.assert_invalid(package, "asset sizeBytes mismatch")

    def test_forbidden_secret_or_machine_keys_are_rejected(self):
        package = load_fixture()
        package["customers"][0]["contact"]["api_token"] = "not allowed"
        refresh_hash(package)
        self.assert_invalid(package, "forbidden secret")

        package = load_fixture()
        package["documents"][0]["title"] = "C:\\Users\\Example\\Documents\\leak.json"
        refresh_hash(package)
        self.assert_invalid(package, "forbidden machine path value")

    def test_customer_projection_and_revision_evidence_are_required(self):
        package = load_fixture()
        package["revisions"][0]["sourceEvidence"].pop("showTheMath")
        refresh_hash(package)
        self.assert_invalid(package, "Show the Math")

        package = load_fixture()
        package["customerProjections"][0]["projection"]["view"] = "internal"
        refresh_hash(package)
        self.assert_invalid(package, "customer-safe view marker")

    def test_customer_projection_rejects_internal_pricing_fields(self):
        package = load_fixture()
        package["customerProjections"][0]["projection"]["lineItems"][0]["profitCents"] = 1000
        refresh_hash(package)
        self.assert_invalid(package, "internal-only field")

    def test_revision_totals_are_required_integer_cents(self):
        package = load_fixture()
        package["revisions"][0]["totals"]["totals"].pop("final_total_cents")
        refresh_hash(package)
        self.assert_invalid(package, "final_total_cents")

        package = load_fixture()
        package["revisions"][0]["totals"]["totals"]["profit_cents"] = "4500"
        refresh_hash(package)
        self.assert_invalid(package, "profit_cents")

    def test_engine_identity_and_sha256_are_enforced(self):
        package = load_fixture()
        package["revisions"][0]["engineWheelSha256"] = "not-a-sha"
        with self.assertRaisesRegex(ValidationError, "schema validation failed"):
            validate_json_schema(package)

        package = load_fixture()
        package["revisions"][0]["sourceEvidence"]["engine"]["engineSourceCommit"] = "different"
        refresh_hash(package)
        self.assert_invalid(package, "engineSourceCommit")

    def test_pdf_revision_template_and_branding_evidence_must_match(self):
        package = load_fixture()
        package["pdfOutputs"][0]["revisionPortableId"] = package["revisions"][1]["portableId"]
        refresh_hash(package)
        self.assert_invalid(package, "PDF output revision belongs to another document|pdf output revision belongs to another document")

        package = load_fixture()
        package["pdfOutputs"][0]["templateVersion"] = 2
        refresh_hash(package)
        self.assert_invalid(package, "template version")

        package = load_fixture()
        package["pdfOutputs"][0]["brandingVersion"] = 2
        refresh_hash(package)
        self.assert_invalid(package, "branding version")

    def test_template_inheritance_cycles_are_rejected(self):
        package = load_fixture()
        package["templates"][0]["parentTemplatePortableId"] = package["templates"][0]["portableId"]
        refresh_hash(package)
        self.assert_invalid(package, "template inheritance contains a cycle")

    def test_nonfinite_json_numbers_are_rejected_on_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nonfinite.json"
            path.write_text('{"value": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "non-finite JSON number"):
                _load_package(path)


if __name__ == "__main__":
    unittest.main()
