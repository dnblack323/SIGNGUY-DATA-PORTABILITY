# SignGuy Slim Portable Contract - Version 1

## Purpose

Version 1 packages move only authorized Slim Version 1 data between compatible
empty Slim tenants and, later, into a new empty MVP tenant through the separately
authorized MVP importer. The contract is independent of Slim application code.

## Contract Identity

- Contract name: `signguy-slim-portable`
- Contract version: `1.0.0`
- Schema: `schemas/signguy-slim-portable-v1.schema.json`
- Stable portable ID prefix: `sgp_v1_`

Portable IDs are immutable across export, restore, and MVP import. The package
must never contain credentials, secrets, sessions, provider tokens, private URLs,
or production database identifiers.

## Version 1 Entity Coverage

| Entity | Version 1 support | Notes |
| --- | --- | --- |
| Tenant settings | Required | Includes shop name, timezone, and simple tax rate. |
| Safe user references | Required | Assignment/author references only; no auth credentials or sessions. |
| Customers | Required | Includes contact, business name, tax exemption, active state, and internal notes. |
| Estimates | Required | UI term is Estimate; MVP importer maps to canonical Quote. Preserves document dates, conversion link, tax snapshot, and totals. |
| Estimate Items | Required | Preserves quantity, manual unit price, line total, taxable state, notes, position, due date, assignment, and production-required state. |
| Orders | Required | Preserves manually entered totals and source estimate link. |
| Order Items | Required | Manual unit price only; production stage and completion are separate fields. |
| Work Orders | Required | Minimal canonical production representation for order/customer links, item snapshots, stage/status, assignment, due dates, lifecycle timestamps, and notes. |
| Invoices | Required | One invoice per order; document status and payment status remain distinct. |
| Calendar events | Required | Event completion does not complete production. |
| Reminders | Required | Due/late/follow-up reminders only. |
| Notes | Required | Internal notes only in Version 1. |
| Attachments | Required | Ordinary files with hashes; no camera or annotation derivatives. |
| Audit events | Required | Minimal provenance for creation, conversion, assignment, status, completion/reopen, attachment, and import/export-relevant events. |

## Compatibility Rules

- Import/restore targets must be empty for business data.
- Unknown future fields are rejected for Version 1 packages.
- Unknown future entity arrays are rejected for Version 1 packages.
- `contains_secrets` must be false.
- Manifest counts, attachment counts, attachment bytes, and file inventory must
  match the package records.
- Calendar completion must not mutate production completion.
- Historical totals are authoritative and must not be recalculated by the MVP
  Pricing Engine during upgrade import.
- Attachment paths are package-relative logical paths, not local filesystem
  absolute paths or object-storage private URLs.
- Quantity is represented as a decimal string with up to four fractional digits.
  Line totals are integer cents and remain authoritative; the validator checks
  the preserved line total against unit price times quantity using decimal
  arithmetic for simple manually priced Version 1 lines.
- Billing addresses are strict objects with line1, optional line2, city, state,
  postal_code, and country only.
- Type-correct relationships and same-tenant relationships are required.

## Validation Scope In Part 1

The Part 1 validator performs JSON Schema validation through pinned
`jsonschema`, then independent semantic validation for package-shape,
required-section, portable-ID, manifest count, same-tenant, type-correct
relationship, duplicate-ID, forbidden-secret-key, totals, file inventory, and
calendar / production separation checks. Archive hardening, encryption
verification, rollback, empty-target enforcement, and real attachment checksum
verification belong to Version 1 Parts 5-7.
