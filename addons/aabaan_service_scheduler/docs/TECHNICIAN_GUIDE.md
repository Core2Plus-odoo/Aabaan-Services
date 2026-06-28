# Technician Workflow Guide — Aabaan Service Scheduler

This guide is for field technicians and the supervisors who oversee them. It
covers what to do at each stage of a service visit, and what to check before
moving it forward.

## Where to work

Technicians use the **Aabaan Scheduler** app (not the CEO Dashboard, which is
management-only):

- **Team Status** (kanban grouped by technician) — see what's assigned to you
  today.
- **Scheduling Dashboard** (calendar) — see your visits by date/time.
- **Service Visits** (list) — open any visit directly to update it.

## Visit states and what to do in each

| State | Meaning | What the technician/supervisor does |
|---|---|---|
| **To Schedule** (`draft`) | Visit created from a contract, no time/technician confirmed | Supervisor assigns technician(s) and a date/time (manually or via **Auto Schedule**) |
| **Scheduled** | Technician and time slot confirmed | Technician sees the visit on Team Status / calendar; travels to site at the planned time |
| **In Progress** | Technician has started on-site work | Click **Start** when work begins |
| **Done** | Work completed | Technician records the visit details (see checklist below) and clicks **Done** |
| **Missed** | Visit did not happen as planned | Supervisor/technician marks **Missed** and reschedules a new visit if needed |
| **Cancelled** | Visit no longer required | Supervisor/technician marks **Cancelled** |

After **Done**, the visit is not closed yet — it still needs supervisor
**approval** (see below).

## Field checklist — before marking a visit "Done"

Complete all of the following on the visit form before clicking **Done**:

- [ ] **Before Notes** — site condition / issue observed on arrival.
- [ ] **Materials Used** — chemicals, parts or consumables used, with
      quantity if relevant.
- [ ] **After Notes** — work actually performed and outcome.
- [ ] **Next Recommendation** — anything the customer or office should follow
      up on (e.g. re-treatment needed, access issue, customer request).
- [ ] Confirm the **Planned Date/Start/End** reflect when the work actually
      happened (update them if the visit ran outside the originally scheduled
      window).

Only after these are filled in should the technician click **Done** —
`completion_date` is stamped automatically at that point.

## Supervisor approval checklist

A Technician Supervisor or Sales Manager reviews every visit in **Done**
state from **Aabaan Scheduler → Approvals** before clicking **Approve**:

- [ ] Before/After Notes are filled in and make sense together.
- [ ] Materials Used is recorded (if the service type normally requires
      chemicals/parts).
- [ ] Next Recommendation is reviewed — escalate to sales/office if it implies
      a new contract, re-visit, or customer issue.
- [ ] Completion date is reasonable (not before the planned date, not far in
      the future).

Approval cannot happen before a visit reaches **Done**, and is restricted to
the Technician Supervisor and Sales Manager groups
(`action_approve` raises an Access Error for anyone else).

## Missed visits

If a technician cannot complete a visit as planned (customer not available,
access denied, etc.), mark it **Missed** rather than leaving it stuck in
**Scheduled**/**In Progress** — this keeps the CEO Dashboard's missed-visit
rate accurate and signals the office to follow up and reschedule.
