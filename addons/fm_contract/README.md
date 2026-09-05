# FM Contract

**A contract is a sale order.** This module puts the facility-management
layer on `sale.order` and keeps the older `fm.contract` model alive,
read-only, until it is retired. Depends on `fm_asset` and `sale_management`.

## What is code, what is configuration

| Thing | Where it lives |
|---|---|
| FM fields on the order (`is_fm_contract`, term, ACV, assets, SLA, health, printed wording) | Code — `models/sale_order.py` |
| Printed-agreement wording rules, shared by every model that can be a contract | Code — `models/fm_agreement_mixin.py` |
| Contract numbering | Configuration — the `fm.contract` sequence (`AMC-####`), editable in Settings |
| Which wording a service starts from | Configuration — Agreement Wording Templates |
| SLA targets per severity | Configuration — SLA Rules on each contract |

## Decision log (brief §2.2 — standard-first hierarchy)

| Model | Decision | Rationale |
|---|---|---|
| the contract itself | **`sale.order` with FM fields** (hierarchy step 2) | The order already carries the customer, priced lines, currency, taxes, signature, invoicing and delivery status. FM adds only what a sale order has no opinion about: covered assets, SLA, renewal and the printed agreement. |
| lifecycle | **Starts where `sale.order.state` stops** | Draft / sent / confirmed / cancelled is what the order's own state means. `fm_lifecycle` covers only what comes after: Active, In Renewal, Expired, Terminated. Two status fields describing the same thing are two fields free to disagree. |
| requiredness | **In the view, not the column** | These fields are mandatory *because a record is a contract*, and most orders in this database never will be. A required column would stop every ordinary quotation saving. |
| `fm.contract` | **Frozen, being retired** | Wrapped a sale order by delegation. Nothing creates it; it stays readable while dependants are re-pointed. |
| `fm.sla.rule` | **New model** | Per-contract response/resolution targets by severity — no Odoo precedent. |
| `fm.contract.service.item` | **New model** | Inclusion/exclusion catalog for scope checks. |
| `fm.contract.penalty` | **New model** | Penalty/credit clauses. |

## The workflow

1. Raise a quotation in **Sales** for the customer, with the priced service lines.
2. Tick **Facility Management Contract**. A contract number is issued then —
   not at creation, so ordinary quotations never burn one.
3. Fill the **FM Contract** and **Printed Agreement** tabs.
4. **Confirm the order.** That is what makes the contract Active: one action,
   one meaning, and no window where the order is confirmed but the contract
   is not.

`fm.sla.rule`, `fm.contract.penalty` and `fm.contract.agreement.line` each
carry both an `order_id` and a legacy `contract_id`. Neither is required
while both exist: a row belongs to exactly one of them, so requiring either
would make the other impossible.

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
