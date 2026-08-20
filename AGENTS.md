# SignGuy Data Portability Agent Instructions

## Repository Boundary

- This repository owns portable schemas, compatibility rules, validators,
  mapping documents, and sanitized fixtures only.
- Do not add application runtime code, customer data, secrets, credentials,
  sessions, provider tokens, or private URLs.
- Keep Slim application changes in `SIGNGUY-SLIM`; never mix Slim files and
  portability files in one commit or pull request.
- Use `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP-REFERENCE` only as a
  read-only reference. Its push URL must remain `DISABLED`.
- Do not modify the regular `SIGNGUY-MVP` repository except during a separately
  authorized MVP importer part.

## Scope Boundary

- Current authorized scope is Version 1 Part 1 correction only.
- Do not create Version 1 export/restore implementation, MVP importer code, or
  any Version 2 schema/entities/scaffolding.

## Required Validation

Run these before handoff after contract changes:

```powershell
python -m pip install -r requirements.txt
python tools\validate_schema.py
python -m unittest discover -s tests
python tools\validate_portable_package.py fixtures\golden\v1-empty-package.json
python tools\validate_portable_package.py fixtures\golden\v1-sample-package.json
```
