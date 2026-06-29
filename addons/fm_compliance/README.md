# FM Compliance

GCC regulatory compliance (brief §5.6, §6.6). Depends on `fm_workorder`
(for `fm.asset`, `fm.checklist.template` and `fm.workorder`).

## Models (all new — no Odoo precedent)
- `fm.compliance.regime` — a regulatory regime (authority, code, applicable asset categories) with task templates.
- `fm.compliance.task.template` — recurring compliance task definition.
- `fm.compliance.certificate` — per asset/location certificate with computed `state` (valid / expiring_soon / expired / renewed).

## Behaviour (§6.6)
Daily cron `_cron_certificate_watchdog`: for certificates within 30 days of
expiry (and not renewed) that have no open related work order, it raises a
`compliance` work order and links it on the certificate. Expired certificates
flip to `expired` via the stored `state` compute.

## Deferred
- Seeded regime data (Civil Defence/DEWA/Municipality/TASNEEF, KSA/Oman/…) per brief §9.4 — added as `data/` once the catalog is confirmed.
- Notification escalation (`fm.notification.rule`) and certificate PDF + QR — land with `fm_integrations` / the report layer.
- Customer on generated WOs defaults to the company partner until `asset.contract_id` exists.
