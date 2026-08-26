# SignGuy Data Portability

Versioned portable data contract for SignGuy Slim backup/restore and the later
Slim-to-MVP upgrade importer.

This repository contains schemas, compatibility rules, validators, mapping
documentation, and sanitized fixtures only. It must not contain customer data,
application secrets, or full application code.

## Version 1 Part 1 Contents

- `schemas/signguy-slim-portable-v1.schema.json`
- `docs/V1_PORTABILITY_CONTRACT.md`
- `docs/V1_MVP_MAPPING_FOUNDATION.md`
- `fixtures/golden/v1-empty-package.json`
- `fixtures/golden/v1-sample-package.json`
- `fixtures/invalid/v1-invalid-file-inventory.json`
- `tools/validate_portable_package.py`
- `tools/validate_schema.py`
- `tests/test_validate_portable_package.py`

## Pricing Profile v1 Proposal

Phase 2E adds a separate pricing settings portability foundation:

- `schemas/signguy-pricing-profile-v1.schema.json`
- `docs/PRICING_PROFILE_V1_PROPOSAL.md`
- `fixtures/golden/pricing-profile-v1-sample.json`
- `fixtures/invalid/pricing-profile-v1-secret-leak.json`
- `tools/validate_pricing_profile.py`
- `tests/test_validate_pricing_profile.py`

This contract is separate from the Slim business-data Version 1 package. It
excludes customers, estimates, orders, invoices, payments, credentials, license
data, private URLs, product-specific UI state, and raw SQLite files.

## Validation

```powershell
python -m pip install -r requirements.txt
python tools/validate_schema.py
python -m unittest discover -s tests
python tools/validate_portable_package.py fixtures/golden/v1-empty-package.json
python tools/validate_portable_package.py fixtures/golden/v1-sample-package.json
python tools/validate_pricing_profile.py fixtures/golden/pricing-profile-v1-sample.json
```
