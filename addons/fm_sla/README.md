# FM SLA & Health

SLA breach detection, contract health scoring and WO→invoice automation
(brief §6.2, §6.4, §6.5). Depends on `fm_workorder`.

## What it adds

| Area | Behaviour |
|---|---|
| **SLA actuals** (§6.2) | `sla_response_actual_min` (create→acknowledge), `sla_resolution_actual_min` (create→sign-off minus paused minutes) on `fm.workorder`. |
| **SLA status** | `sla_response_status` / `sla_resolution_status` (not_started/on_track/at_risk/breached/met). At-risk at 80% of target consumed. |
| **Watchdog** | 5-minute cron `_cron_refresh_sla` re-evaluates in-flight clocks (the status computes use `now()`). |
| **Contract health** (§6.5) | `_compute_fm_health` scores 0–10 over the last 90 days (SLA 40%, CSAT 20%, open P1/P2 20%) and sets `health_band`. Nightly cron + immediate recompute on sign-off. |
| **WO → invoice** (§6.4) | On sign-off of a **break-fix** WO, a draft `account.move` is created from parts + labor lines and linked on `invoice_id`. AMC contracts are covered by the retainer (no per-WO invoice). |

## Decision log (brief §2.2)
- Extends `fm.workorder` / `fm.contract` via `_inherit` — no new models.
- `action_stage_change` is wrapped (super then side-effects) so the sign-off
  hook stays in this module without touching the core state machine.

## Deferred / simplifications
- Invoice lines use cost as `price_unit` (no markup field yet) and rely on the
  customer's default taxes; explicit VAT 5% / markup % land with the billing
  config. AMC non-comprehensive out-of-scope billing (scope check) is a follow-up.
- Business-hours-only SLA calendars (`fm.sla.rule.business_hours_only`) are not
  yet applied to the elapsed-time math — calendar-aware durations are a follow-up.
