# Version 1 MVP Mapping Foundation

This document defines the first-pass mapping targets for the later Version 1
Part 6 MVP importer. It is not MVP importer code and does not authorize changes
to the MVP repository.

| Portable entity | MVP target | Required import behavior |
| --- | --- | --- |
| Customer | `Customer` | Create same-tenant customer with contact/business data and tax-exemption metadata where supported. |
| Estimate | `Quote` | Preserve Estimate number/status/totals; expose as canonical MVP Quote. |
| Order | `Order` | Preserve source Quote link, status, due date, manual totals, and internal notes. |
| Order Item | `OrderItem` and Work Order linkage where production is required | Preserve manual unit price, line total, production-required flag, stage, completion, due/scheduled fields. Do not run Pricing Engine. |
| Invoice | `Invoice` | Enforce one invoice per order and keep document status separate from financial status. |
| Calendar Event | `CalendarEvent` | Preserve schedule records while keeping completion distinct from production completion. |
| Reminder | In-app notification/reminder model | Preserve due/late/follow-up state and source record. |
| Note | Internal note/audit-compatible record | Never expose internal notes to customers. |
| Attachment | File/attachment model and object storage | Stage package files, verify checksums, then persist tenant-scoped attachment metadata. |

## Required Later Import Gates

- Dry run before writes.
- Explicit confirmation after dry-run report.
- New empty MVP tenant only.
- Transactional import with rollback.
- Idempotency keyed by portable ID.
- Unsupported records reported before confirmation.
- No Stripe transactions, customer portal accounts, SendGrid activity, AI
  records, payroll/time records, webstores, wrap lab, or pricing recalculation.
