# SignGuy Pricing Profile v1 Proposal

`signguy-pricing-profile-v1` is a separate portability contract for approved pricing settings. It is not part of the Slim business-data Version 1 schema and it is not a raw database export.

## Scope

Included:

- Stable pricing keys.
- Units and typed values.
- Shop rate inputs.
- Labor, overhead, and equipment settings.
- Material and component values.
- Accepted Starter values.
- Shop overrides.
- Provenance, source class, pack version, and review state.

Excluded:

- Customers, estimates, orders, invoices, and payments.
- Credentials, tokens, license data, private URLs, and environment values.
- Product-specific UI state.
- Raw SQLite files or raw application database documents.

## Import Requirements For Later Consumers

Slim and MVP consumers must implement this contract with:

- Schema validation before import.
- Dry-run preview before mutation.
- Add, Update, Skip, Conflict, and Unsupported reporting.
- Explicit owner approval before applying changes.
- Transactional import.
- Audit entry.
- Safety backup before mutation.
- Rollback if validation or persistence fails.

## Current Phase 2E Deliverables

- JSON Schema: `schemas/signguy-pricing-profile-v1.schema.json`
- Golden fixture: `fixtures/golden/pricing-profile-v1-sample.json`
- Invalid fixture: `fixtures/invalid/pricing-profile-v1-secret-leak.json`
- Validator: `tools/validate_pricing_profile.py`
- Tests: `tests/test_validate_pricing_profile.py`

This stage defines and validates the shared contract foundation only. It does not modify SIGNGUY-SLIM or SIGNGUY-MVP application code.
