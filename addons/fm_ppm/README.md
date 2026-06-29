# FM PPM

Preventive maintenance schedules (brief §5.4). Depends on `fm_workorder`.

## Decision log (brief §2.2)
- **`fm.ppm.schedule`** — new model (no Odoo precedent for FM PPM cadence/meter triggers).
- Reuses `fm.checklist.template` (defined in `fm_workorder`) rather than redefining it.
- Extends `fm.workorder` with `parent_ppm_schedule_id` (back-link for generated WOs).

## Behaviour
- `next_due` computed from `last_completed`/`create_date` + frequency (day/week/month/quarter/year).
- Daily cron `_cron_generate_ppm_workorders` creates a PPM work order `wo_lead_days` before `next_due`, skipping schedules that already have an open generated WO.

## Notes / deferred
- Meter-based triggers store `meter_threshold`; meter ingestion (BMS/IoT) lands with `fm_integrations`.
- Generated WO `customer_id` defaults to the company partner until `fm_contract` adds `asset.contract_id` to resolve the true customer.
