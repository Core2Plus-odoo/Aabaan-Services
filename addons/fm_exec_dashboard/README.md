# fm_exec_dashboard — Aabaan Executive (CEO) Dashboard

The CEO pack the business already works from, rendered live from the
database instead of assembled by hand each month.

Three sections, chosen from a period preset or a custom range, optionally
narrowed to one branch:

| Section | What it answers |
|---|---|
| **1 · Overview** | Revenue against target, jobs completed, new clients, receivables and overdue; city-and-team table; revenue trend stacked by branch; service-line mix; salesperson performance; receivables aging; job status; largest open balances |
| **2 · Expenses** | Total spend, net profit, net margin, payroll share; monthly expense trend with the revenue line over it; spend by category and by city; expense detail by account |
| **3 · Cash & Bank** | Balance per bank and cash journal, inflow, outflow, net movement, flow trend, recent transactions |

## What is code, what is configuration

**Code (this module):**

- `fm.exec.dashboard` — a read-only `AbstractModel` that aggregates native
  records and computes the chart geometry.
- An OWL client action, its template and one stylesheet.
- `fm.branch.monthly_revenue_target` — the target the Achv % is measured
  against.
- `account.move.branch_id` — the branch dimension for money.

**Configuration (done in Odoo, not here):**

- **Branch targets.** FM → Configuration → Branches → *Monthly Revenue
  Target*. Left at zero, the dashboard shows a dash for Achv %, not a
  fabricated target.
- **Branch on vendor bills.** Customer invoices inherit the branch from
  their sale order automatically. A vendor bill has no order behind it, so
  someone has to say which branch office rent or fuel belongs to — the
  field is on the invoice form.
- **Bank and cash journals.** Section 3 reads whatever journals of type
  bank/cash exist, and their account balances. Nothing to configure beyond
  having them set up properly.

## Why it is a separate module

`fm_ceo_dashboard` reports the **contract portfolio** — ACV/TCV, contract
health, operations load by severity, compliance risk. This one reports
**money** — revenue, expenses, cash. They answer different questions for
the same person, and keeping them apart means neither has to be rebuilt to
change the other. Both can be installed together; both sit under the FM app
root.

## No invented numbers

Every figure is read from posted records:

| Figure | Source |
|---|---|
| Revenue | Posted customer invoices and refunds, `amount_untaxed_signed` |
| Expenses | Posted lines on accounts whose type starts with `expense` — so a payroll journal entry counts, not only a vendor bill |
| Receivables, aging | Unreconciled posted receivable lines, bucketed on `date_maturity` |
| Jobs completed | `project.task` moved into a folded stage inside the period |
| New clients | `res.partner` with `customer_rank > 0` created in the period |
| Service mix | Service line of the `fm.contract` behind each invoice |
| Cash | Balance of each bank/cash journal's default account |

Where a number cannot be derived the dashboard shows **a dash, not a zero**
— zero is a claim, a dash is not. That applies to a branch with no target,
a period with no prior period to compare against, and any KPI whose inputs
are missing.

Three deliberate omissions:

- **No per-salesperson target.** None exists in the database. The chart
  shows revenue invoiced per person and stops there.
- **Expenses are not spread across branches.** Only spend on a document that
  names its branch is attributed; the rest is reported as unallocated, with
  the amount stated. An allocation rule for shared overheads is a management
  decision, not something a dashboard should invent.
- **Cash is not branch-scoped.** A bank account belongs to the company, not
  an emirate, so the branch filter deliberately does not apply on that tab.

## Periods

Presets: this/last week, month, quarter and year, plus a custom range. A
"this" preset runs to **today**, not to the end of the calendar period —
three weeks of this month measured against a full prior month would flatter
every result.

Every "vs prior period" compares against a window of the **same length**
immediately before the selected one, and the footer states both windows so
the comparison is never a mystery.

## No charting library

CLAUDE.md §4 records that OWL client-action dashboards in this repo break on
stale asset bundles. So this module loads nothing: bars are CSS
percentages, and the pie arcs and the trend polyline are SVG paths computed
in Python and sent down with the data. Colours come from `fm_branding`'s
`--fm-*` tokens, including the per-service colours, so a service reads the
same here as everywhere else in the platform.
