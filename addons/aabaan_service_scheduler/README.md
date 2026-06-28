# Aabaan Service Scheduler

Scheduling and service-delivery management for pest control, water tank cleaning
and similar recurring on-site services. Covers the full lifecycle: contract →
visit generation → scheduling → field execution → supervisor approval, plus a
CEO Dashboard for management oversight.

## Security groups

| Group | Who | Access |
|---|---|---|
| `base.group_user` (Internal User) | Office staff / coordinators | Create/read/write contracts and visits |
| `group_aabaan_service_supervisor` (Technician Supervisor) | Field supervisors | Above, plus approve completed visits, assign technicians, auto-schedule |
| `group_aabaan_service_ceo` (CEO / Executive) | Management | Read-only access to contracts/visits, plus the standalone **CEO Dashboard** app |
| `sales_team.group_sale_manager` (Sales Manager) | Sales/ops managers | Full access everywhere, including the CEO Dashboard |

Assign these under **Settings → Users & Companies → Users**, in the "Service
Scheduler" section of a user's Access Rights tab.

## End-to-end workflow

1. **Create a Service Contract** (`Aabaan Scheduler → Contracts`): customer,
   service type, area/emirate, start/end date, visit frequency
   (1/2/4/6/12/24/36 or custom), contract value and preferred technicians.
   The contract reference is auto-numbered (`SC/<year>/0001`).
2. **Generate Visits**: click **Generate Visits** on the contract form. This
   creates one `aabaan.service.visit` record per frequency count, evenly
   spaced between the contract's start and end date, pre-filled with the
   customer, service type, area/emirate, company and preferred technicians.
   Re-running is blocked once visits exist (delete them first to regenerate).
3. **Schedule**: use **Auto Schedule** (`Aabaan Scheduler → Auto Schedule`) to
   bulk-assign available technicians and time slots to draft visits in a date
   range, or assign manually from the Service Visits list/kanban/calendar.
4. **Execute**: technicians/supervisors move a visit through
   To Schedule → Scheduled → In Progress → Done (or Missed/Cancelled),
   recording before/after notes, materials used and recommendations.
5. **Approve**: a Technician Supervisor or Sales Manager approves completed
   visits from `Aabaan Scheduler → Approvals`.

## Visit journey / flow

Every visit moves through a single state machine, visualised end-to-end in
**CEO Dashboard → Operations → Visit Journey** (kanban grouped by status):

```
draft (To Schedule) → scheduled → in_progress → done → [approved]
                                              ↘ missed
                                              ↘ cancelled
```

- **To Schedule (`draft`)** — created by contract visit generation; no
  technician/time slot confirmed yet.
- **Scheduled** — technician(s) and a planned date/time window are assigned,
  either manually or via the Auto Schedule wizard.
- **In Progress** — the technician has started the visit on-site.
- **Done** — the technician has completed the visit and recorded completion
  date, materials used, before/after notes and a recommendation. Visits in
  `done` are not yet final until approved.
- **Missed / Cancelled** — terminal states for visits that didn't happen as
  planned.
- **Approval gate** — a visit in `done` only becomes fully closed once a
  Technician Supervisor or Sales Manager clicks **Approve**
  (`Aabaan Scheduler → Approvals`, or the CEO Dashboard's Pending Approvals
  item), which stamps `approved_by`/`approved_date`. Approval is restricted to
  those two groups and only allowed once the visit is `done`.

## CEO Dashboard

A standalone top-level app ("CEO Dashboard"), separate from the operational
Aabaan Scheduler menu, visible only to `group_aabaan_service_ceo` and Sales
Managers:

### Financial Overview

Real accounting KPIs sourced from posted `account.move` entries (read-only,
no data duplication with Accounting):

- **Revenue & Receivables** — pivot/graph/list of posted customer invoices
  and credit notes, by customer and month, with untaxed, total and
  outstanding-residual (receivable) amounts.
- **Cost & Payables** — pivot/graph/list of posted vendor bills and refunds,
  by vendor and month, with untaxed, total and outstanding-residual
  (payable) amounts.

These require the Accounting app to be installed and invoices/bills to be
posted; figures are blank until then.

### Contracts Management

- **Contracts Overview** — pivot/graph of contract value and billing-cycle
  amount by company, service type, emirate and status.
- **All Contracts** — full contract list for management review, independent
  of the operational Contracts menu.
- **Expiring Contracts** — active contracts ending within 30 days, for
  renewal follow-up.

### Operations

- **Operations & Visits** — visit volume/duration by status, grouped by
  company, service type, emirate and technician, with a monthly trend graph.
- **Visit Journey** — kanban/calendar/list visualising every visit's status
  across the full flow described above.
- **Technician Performance** — workload and completion/missed-visit rate per
  technician.

### Pending Approvals

Completed visits awaiting supervisor sign-off.

### Multi-company readiness

`company_id` exists on both Contracts and Visits today (defaulting to the
current company) so every dashboard view already supports grouping/filtering
by company. The field and "Company" filters stay hidden while there is only
one company; once a second company is added they appear automatically and the
CEO Dashboard becomes a consolidated multi-company view with no further
changes required.

## Go-live checklist

See [`docs/GO_LIVE_CHECKLIST.md`](docs/GO_LIVE_CHECKLIST.md).
