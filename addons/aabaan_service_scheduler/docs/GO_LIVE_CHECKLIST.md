# Go-Live Checklist — Aabaan Service Scheduler

## 1. Install / upgrade
- [ ] Module upgrades with no errors in `odoo.log` / `update.log` (check for
      `RELAXNG_ERR_*`, `ParseError`, or `Failed to load registry`).
- [ ] `aabaan_service_scheduler` shows the expected version in
      **Apps → Aabaan Service Scheduler**.

## 2. Master data
- [ ] Default Services (`product.product`) created for each service type used
      (Pest Control, Water Tank Cleaning, Cleaning, Termite, Other).
- [ ] Technicians created as `hr.employee` records.
- [ ] Customers (`res.partner`) exist with phone numbers populated (the
      contract's Phone field is read from the customer).

## 3. Security
- [ ] Office staff/coordinators are Internal Users (`base.group_user`).
- [ ] Field supervisors are in **Technician Supervisor**
      (`group_aabaan_service_supervisor`).
- [ ] The CEO/management are in **CEO / Executive**
      (`group_aabaan_service_ceo`) — required to see the standalone
      **CEO Dashboard** app.
- [ ] Sales/ops managers are in **Sales Manager**
      (`sales_team.group_sale_manager`) for full access.

## 4. Contracts → visits
- [ ] Create a test contract, confirm the auto-numbered reference
      (`SC/<year>/0001`).
- [ ] Click **Generate Visits**, confirm the right number of visits is
      created and evenly spread between start/end date.
- [ ] Confirm visits inherit customer, service type, area/emirate and
      preferred technicians from the contract.

## 5. Scheduling
- [ ] Run **Auto Schedule** over a date range with available technicians,
      confirm no double-booking (a technician is never assigned two
      overlapping visits).
- [ ] Confirm the **Scheduling Dashboard** (calendar) and **Team Status**
      (kanban grouped by technician) reflect the same data.

## 6. Field execution & approval
- [ ] Move a visit through To Schedule → Scheduled → In Progress → Done.
- [ ] Confirm a non-supervisor/non-manager user cannot approve a visit
      (`action_approve` raises an Access Error).
- [ ] Approve the visit as a Technician Supervisor or Sales Manager, confirm
      `approved_by` / `approved_date` are stamped.

## 7. CEO Dashboard
- [ ] Log in as a CEO/Executive (or Sales Manager) user, confirm the
      standalone **CEO Dashboard** app appears (separate from the
      operational **Aabaan Scheduler** app).
- [ ] Confirm **Revenue & Contracts**, **Expiring Contracts**,
      **Operations & Visits**, **Technician Performance** and
      **Pending Approvals** all load with real data.
- [ ] Confirm a plain Internal User does **not** see the CEO Dashboard app.

## 8. Multi-company (when a second company is added later)
- [ ] Confirm `Company` field/filter appears on Contracts and Visits.
- [ ] Confirm CEO Dashboard pivots group correctly by company.
