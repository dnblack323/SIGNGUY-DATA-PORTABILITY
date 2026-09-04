# Price Lab Sales Documents Portable Package V1

Status: Phase 5D contract.

This contract transfers selected Price Lab Estimates, Quotes, and Invoices between local Price Lab installations. It is not the Slim backup package and it is not a customer-facing PDF. A package may contain customer information and internal pricing information, so the manifest must declare both.

## Ownership

Data Portability owns:

- `schemas/price-lab-sales-documents-v1.schema.json`;
- `tools/validate_price_lab_sales_documents.py`;
- deterministic canonicalization and content hashing rules;
- sanitized valid and invalid fixtures;
- compatibility documentation.

Price Lab owns:

- Electron file selection and save dialogs;
- local SQLite export/import history;
- document ID remapping into a destination shop;
- customer workflow and dry-run preview;
- atomic apply behavior.

The shared pricing engine is not involved in Phase 5D because prices, totals, and calculation evidence are frozen and transferred without recalculation.

## Package Shape

The top-level package contains:

- `manifest`;
- `customers`;
- `projects`;
- `documents`;
- `revisions`;
- `customerProjections`;
- `brandingProfiles`;
- `templates`;
- `pdfOutputs`;
- `assets`.

Portable IDs use the `plsd_v1_*` namespace and are independent of local SQLite IDs. Records also preserve their original local ID in `sourceLocalId` for traceability only.

## Manifest

The manifest records:

- contract name and version;
- format/schema version;
- export identity and creation date;
- source application version;
- source shop portable ID;
- currency;
- record counts;
- deterministic `contentSha256`;
- supported Price Lab schema compatibility range;
- customer-information and internal-pricing-information warnings;
- explicit exclusions for secrets, raw databases, and machine-specific paths;
- optional signature metadata when a package already carries it.

## Canonical Hash

The deterministic content hash is SHA-256 of the canonical JSON package with:

- object keys sorted;
- compact JSON separators;
- UTF-8 encoding;
- `manifest.contentSha256` replaced with sixty-four zeroes before hashing.

Changing any record, frozen evidence, customer projection, asset, or metadata changes the hash.

## Preservation Rules

Valid packages preserve:

- document revisions;
- finalized pricing snapshots;
- customer-safe projections;
- conversion ancestry;
- customer and project references;
- template and branding evidence;
- generated PDF metadata;
- required logo assets with MIME type, byte count, and SHA-256.

Packages must exclude credentials, secrets, tokens, machine-specific paths, raw databases, temporary files, and live application settings.

## Validation

The validator performs JSON Schema validation and semantic checks for:

- manifest counts and compatibility;
- duplicate portable IDs;
- deterministic content hash;
- document, revision, projection, template, branding, PDF, and asset relationships;
- missing conversion ancestry;
- logo asset hash/size consistency;
- forbidden secret-like or path-like keys;
- unsupported format versions;
- customer projection view markers;
- revision totals, engine identity, and Show the Math evidence.

Run:

```powershell
python tools/validate_price_lab_sales_documents.py fixtures/golden/price-lab-sales-documents-v1-sample.json
```
