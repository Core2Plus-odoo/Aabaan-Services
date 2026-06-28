# Aabaan Service Scheduler

## Module Metadata

- Technical Name: `aabaan_service_scheduler`
- Category: `Services`
- License: `LGPL-3`
- Version: `19.0.1.0.0`
- Target: Odoo `19.0+e` Enterprise Edition
- Database expiration: July 28, 2026

## Purpose

This addon gives Aabaan an easy Odoo scheduler for recurring service work:

- Pest Control AMC contracts
- Water Tank Cleaning AMC contracts
- One-off or custom cleaning service visits
- Technician assignment
- Calendar-based dispatch
- Service completion notes
- Missed visit tracking
- Renewal visibility

## Daily Workflow

1. Create or import a service contract.
2. Select customer, service type, start date, end date, value, and frequency.
3. Click **Generate Visits**.
4. Open **Aabaan Scheduler > Service Visits**.
5. Assign technicians and schedule start/end time.
6. Use the kanban or calendar view to dispatch daily jobs.
7. Mark each visit as **Done**, **Missed**, or **Cancelled**.
8. Review contracts marked **Renewal Due** before expiry.

## Scheduler Features

- Contract frequencies: 1, 2, 4, 6, 12, 24, 36, or custom visits
- Automatic visit generation across contract duration
- Preferred technician assignment from contract to generated visits
- Technician conflict detection for overlapping scheduled windows
- Kanban board grouped by visit state
- Calendar view for weekly planning
- Cron job to mark past incomplete visits as missed
- Cron job to expire contracts after end date
- Printable service visit report
- Chatter and activities for follow-up

## Deployment Note

If the database is on Odoo.sh or self-hosted Odoo, place `addons/aabaan_service_scheduler` in the custom addons repository and update the app list.

If the database is standard Odoo Online, custom Python addons usually cannot be installed. In that case, implement the same workflow with Odoo Studio custom models or move the database to Odoo.sh.
