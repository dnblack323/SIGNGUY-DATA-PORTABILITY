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
| Customers | Required | Includes contact, business name, tax exemption, active state, and internal notes. |
| Estimates | Required | UI term is Estimate; MVP importer maps to canonical Quote. |
| Orders | Required | Preserves manually entered totals and source estimate link. |
| Order Items | Required | Manual unit price only; production stage and completion are separate fields. |
| Invoices | Required | One invoice per order; document status and payment status remain distinct. |
| Calendar events | Required | Event completion does not complete production. |
| Reminders | Required | Due/late/follow-up reminders only. |
| Notes | Required | Internal notes only in Version 1. |
| Attachments | Required | Ordinary files with hashes; no camera or annotation derivatives. |

## Compatibility Rules

- Import/restore targets must be empty for business data.
- Unknown future fields are rejected for Version 1 packages.
- Unknown future entity arrays are rejected for Version 1 packages.
- `contains_secrets` must be false.
- Calendar completion must not mutate production completion.
- Historical totals are authoritative and must not be recalculated by the MVP
  Pricing Engine during upgrade import.
- Attachment paths are package-relative logical paths, not local filesystem
  absolute paths or object-storage private URLs.

## Validation Scope In Part 1

The Part 1 validator performs package-shape, required-section, portable-ID,
same-tenant, relationship, duplicate-ID, forbidden-secret-key, and calendar /
production separation checks. Archive hardening, encryption verification,
rollback, empty-target enforcement, and real attachment checksum verification
belong to Version 1 Parts 5-7.
