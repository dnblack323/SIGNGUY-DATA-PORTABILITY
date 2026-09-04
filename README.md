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
- [Pricing Profile v1 Target Mappings](docs/PRICING_PROFILE_V1_TARGET_MAPPINGS.md)
- `fixtures/golden/pricing-profile-v1-sample.json`
- `fixtures/invalid/pricing-profile-v1-secret-leak.json`
- `tools/validate_pricing_profile.py`
- `tests/test_validate_pricing_profile.py`

This contract is separate from the Slim business-data Version 1 package. It
excludes customers, estimates, orders, invoices, payments, credentials, license
data, private URLs, product-specific UI state, and raw SQLite files.

## Price Lab Sales Documents v1

Phase 5D adds a separate Price Lab Sales Documents portability contract:

- `schemas/price-lab-sales-documents-v1.schema.json`
- [Price Lab Sales Documents v1 Contract](docs/PRICE_LAB_SALES_DOCUMENTS_V1_CONTRACT.md)
- `fixtures/golden/price-lab-sales-documents-v1-sample.json`
- focused invalid fixtures under `fixtures/invalid/price-lab-sales-documents-v1-*`
- `tools/validate_price_lab_sales_documents.py`
- `tests/test_validate_price_lab_sales_documents.py`

This package transfers selected Price Lab Estimates, Quotes, and Invoices
between local Price Lab installations. It preserves revisions, immutable pricing
snapshots, customer-safe projections, conversion ancestry, branding/template
evidence, and generated PDF metadata. It is not a customer-facing PDF and it may
contain both customer information and internal pricing information.

## Validation

```powershell
python -m pip install -r requirements.txt
python tools/validate_schema.py
python -m unittest discover -s tests
python tools/validate_portable_package.py fixtures/golden/v1-empty-package.json
python tools/validate_portable_package.py fixtures/golden/v1-sample-package.json
python tools/validate_pricing_profile.py fixtures/golden/pricing-profile-v1-sample.json
python tools/validate_price_lab_sales_documents.py fixtures/golden/price-lab-sales-documents-v1-sample.json
```
