# FM Contract

AMC / break-fix / project contracts (brief §5.5). Depends on `fm_asset` and
`sale_management`.

## Decision log (brief §2.2 — standard-first hierarchy)

| Model | Decision | Rationale |
|---|---|---|
| `fm.contract` | **Compose with `sale.order`** via `_inherits` (delegation) | Billing, currency, pricelist and customer come from the standard sales document (hierarchy step 3); FM adds scope, SLA, penalties, lifecycle. |
| `fm.sla.rule` | **New model** | Per-contract response/resolution targets by severity — no Odoo precedent. |
| `fm.contract.service.item` | **New model** | Inclusion/exclusion catalog for scope checks. |
| `fm.contract.penalty` | **New model** | Penalty/credit clauses. |

## Circular dependency handling (contract ↔ work order)

The brief shows `fm.contract.workorder_ids` and a data-driven `health_score`
computed from SLA/CSAT/open-criticals. Those need the `fm.workorder` model,
which **depends on** this module. To avoid a forward dependency:

- `workorder_ids` (One2many) and `workorder_count` are added by **`fm_workorder`**
  via `_inherit='fm.contract'`.
- `health_score` / `health_band` are plain fields here (default *healthy*); the
  nightly scoring algorithm (brief §6.5) is implemented in **`fm_sla`** once
  work-order history exists.

## Security

`ir.model.access.csv` across the FM roles; global multi-company rule scoped via
`sale_order_id.company_id`; account managers see their own contracts while
managers/admins see all (brief §8.2).

> Runtime note: creating an `fm.contract` also creates the delegated
> `sale.order`, so the acting user needs Sales create rights in addition to the
> FM Account Manager group. Configure on the user during onboarding.

## UI

Contract list/form/search with statusbar lifecycle, scope/SLA/penalty/contacts
tabs, and a **Contracts** menu under the FM root. Health-band and state badges
match the dashboard's at-risk semantics (the `dashboard.html` OWL view lands
with the prototypes).
