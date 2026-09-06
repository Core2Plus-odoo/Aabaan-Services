# FM Command Centre (`fm_command_centre`)

Seven tabs, live from the database, every figure one click from its
evidence. Menu: **FM → Command Centre** (FM account managers and up).

## Ported, not rewritten — and it still runs on both platforms

This module came from the `aabaan` build's Executive Command Centre. It was
brought over rather than rebuilt because the queries were already right; what
was wrong for the FM platform was only the *names* of the fields they read.

The same business fact is spelled differently on the two builds. A contract's
service line is `fm_service_line` here and a manual `x_service_line` there.
A visit points back at its contract through `fm_contract_order_id` here and
`sale_order_id` there. Neither set can be imported into the other: one is code
the other build does not have, the other is data this build does not have.

So the dashboard asks for a **concept** and takes the first spelling that
actually exists in the database it is running on — see `FIELD_ALIASES` at the
top of `models/fm_command_centre.py`. A concept nothing answers collapses its
own section into an honest empty state, which is what a missing field already
did; this only widens what counts as an answer.

| Concept | FM build | aabaan build |
|---|---|---|
| Contract service line | `fm_service_line` | `x_service_line` |
| Contract branch / emirate | `branch_id` | `x_emirate_regime` |
| Contract end of term | `fm_end_date` | `end_date` (Subscriptions) |
| Visit type | `fm_wo_type` | `x_visit_type` |
| Visit → contract | `fm_contract_order_id` | `sale_order_id` |
| Visit deadline | `date_deadline` | `x_sla_due` |
| Compliance documents | `fm.compliance.certificate` | `aabaan.contract.document` |

It deliberately does **not** depend on `aabaan_visit_schedule`. That module is
the second visit generator the FM consolidation exists to retire; installing it
here to satisfy a dashboard dependency would put two things back to writing
`project.task` visits for the same customer.

## What is code, what is configuration

| Thing | Where it lives |
|---|---|
| Every figure, and the drill-through domain behind it | Code |
| Which field answers each concept | Resolved at runtime from the database |
| The Emirate analytic plan used for cost-by-branch | Configuration — matched by name (`ilike 'emirate'`) |
| Who can see it | Configuration — the `fm_branding.group_fm_account_manager` group |

Each tab loads on demand, so opening the dashboard never runs the queries
for screens you are not looking at. The period selector (this month / last
month / this quarter / year to date / last 12 months) bounds every
period-scoped figure, and each one is compared against **the previous
window of the same length**, so a delta is always like-for-like.

## The tabs

**Executive Overview** — contracted book, open quotations, pipeline,
receivables (with the overdue slice), customers. A period block showing new
contracts, invoiced net of VAT, cash collected and new leads, each beside
the previous window. Twelve-month invoiced-revenue and cash-collected
trends. Top customers by share of book, plus service-line and emirate mix.

**Field Operations** — visits completed with delta; **first-time-fix rate**
(completed visits that did *not* need a follow-up raised — a real outcome
recorded by the field-ops completion flow, not a proxy); **SLA-clean rate**
(visits planned in the window never escalated); **average time on site**
from real check-in/check-out stamps. Live attention cards (past planned
date, unassigned in the next 7 days, SLA passed, escalated and still open)
which deliberately ignore the period filter — an overdue visit is overdue
today regardless of what window you are looking at. Technicians ranked by
visits completed with real hours on site; open visits by stage, type and
emirate.

**Sales & CRM** — contracts signed with delta, open quotations, quotation
conversion (of the quotations raised in this window, how many are now
confirmed — both sides counted on the same set of records), open pipeline
by stage, **win rate** over decided leads only, lead sources, lost reasons,
contract size mix.

**Finance** — receivables, invoiced net of VAT, cash collected, collection
ratio, and **days sales outstanding with its inputs printed underneath** so
the number can be checked by hand. Five-band ageing measured from the due
date, with "not yet due" kept separate from the overdue bands so the two
are never conflated. Recovery classification (from `aabaan_finance_core`),
invoiced-against-collected side by side, top debtors with their overdue
slice, and outstanding by service.

**Expenses & Margin** — total spend, invoiced net of VAT, what is left
after it, margin, and payroll share. Invoiced against spent over twelve
months, side by side. Where the money went, ranked by expense account —
the chart of accounts *is* the expense category, so there is no parallel
taxonomy to keep in step. Cost by emirate, read off the **Emirate analytic
dimension** rather than off the document, because that dimension is what
`aabaan_finance_core` autofills and enforces on every posting.

Two things this tab does on purpose:

- **Spend is read from the accounts it was booked to, not from vendor
  bills.** A payroll journal entry is a cost. Counting only bills would
  miss the single largest cost this business has.
- **Untagged cost is not spread across branches.** Spend carrying no
  Emirate tag stays out of the branch split, and the tab says so. An
  allocation rule for shared overheads is a management decision, not
  something a dashboard should invent.

**Cash & Bank** — balance across the bank and cash accounts, money in,
money out and net movement for the window, the twelve-month flow, balance
per account, and recent movements.

The balance is **every posted movement up to the end of the window**, while
money in and out are the window alone — a period's opening balance is part
of what is in the bank today. Treating those two as the same measure is the
classic cash-tab error, so the KPI notes say which is which.

Not split by emirate: a bank account belongs to the company, not a branch,
and dividing a shared balance between branches would be a made-up number.

**AMC & Renewals** — renewal buckets and a twelve-month renewal timeline;
**contracts at risk**, each with its reason stated ("3 visits past planned
date · 1 escalated · renews in 40 days"); compliance documents expired or
expiring (from `aabaan_service_contracts`).

## Design rules held throughout

- **Batched aggregation.** Every figure comes from `_read_group` or
  `search_count`. No per-record Python loop over contracts or invoices.
- **Runtime-resolved fields.** The `x_*` fields are manual (Studio) fields
  on this database, and several fields belong to sibling Aabaan modules
  that may not be installed. Every one is guarded — a missing field
  collapses its own section into an honest empty state, and the reason
  appears in the notes strip at the top of the tab.
- **No estimated figures.** Where a number cannot be derived from real
  records it is left out and the reason is stated on screen. An undefined
  delta or percentage renders as a dash, never as 0% or 100% — both of
  which would read as measurements.

## Two things deliberately NOT built

- **Technician utilisation %.** That needs each technician's contracted
  working hours, which this database does not reliably carry. A percentage
  against an assumed 8-hour day would be an invented number, so the tab
  shows **real hours on site** and visits completed instead.
- **A totalled call-out entitlement overage.** `cockpit_unscheduled_over`
  is a computed, non-stored field — it cannot be summed in a query. It
  stays per-contract on the Contract Cockpit tab, and the dashboard says so.

## Note on the contract cockpit fields

All `cockpit_*` fields are computed and **not stored**, so they cannot be
grouped or filtered in a domain, and scoring 600+ contracts one at a time
would be far too slow for a dashboard. The "contracts at risk" list is
therefore rebuilt from the same underlying evidence — overdue visits and
escalations per contract — in two batched queries. Both are real counts,
not a modelled score, which is also why each row can state its own reason.

## What is configuration (native Odoo)

- Lead sources and lost reasons (CRM) — populate them and the Sales tab
  fills in.
- FSM stage names drive the "open visits by stage" breakdown.
