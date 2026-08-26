from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.validate_pricing_profile import ValidationError, validate_pricing_profile

ROOT = Path(__file__).resolve().parents[1]


class PricingProfileValidationTests(unittest.TestCase):
    def load(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_golden_pricing_profile_validates(self):
        profile = self.load("fixtures/golden/pricing-profile-v1-sample.json")
        self.assertEqual(
            validate_pricing_profile(profile),
            ["json schema valid", "excluded data absent", "pricing profile semantics valid"],
        )

    def test_secret_like_or_excluded_fields_are_rejected(self):
        profile = self.load("fixtures/invalid/pricing-profile-v1-secret-leak.json")
        with self.assertRaises(ValidationError):
            validate_pricing_profile(profile)

    def test_packed_sources_require_pack_provenance(self):
        profile = self.load("fixtures/golden/pricing-profile-v1-sample.json")
        del profile["pricing_entries"][0]["provenance"]["pack_version"]
        with self.assertRaisesRegex(ValidationError, "pack_version"):
            validate_pricing_profile(profile)


if __name__ == "__main__":
    unittest.main()
