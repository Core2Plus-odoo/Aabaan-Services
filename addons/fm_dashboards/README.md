# FM Dashboards

Executive dashboard (brief §7.1). Depends on `fm_sla` (for SLA status + health).

## Decision log (brief §2.2)
- **`fm.dashboard.exec`** — new `AbstractModel` data provider (`get_dashboard_data`), read-only aggregation scoped to `env.companies`. Same proven pattern as the command-centre dashboards.
- **OWL client action** `fm_exec_dashboard` consuming the `--fm-*` design tokens (brief §3.1) — built from the §7.1 component spec since the `/prototypes/` HTML is not in the repo.

## Contents
KPI tiles (ACV, active contracts, SLA compliance 90d, open P1/P2, avg CSAT), at-risk contracts table, technician CSAT leaderboard, service mix — under **Facility Management → Dashboards → Executive Dashboard** (FM Manager+).

## Deferred
- **ApexCharts** revenue-trend / SLA-by-severity charts (brief §7.1) — ships KPI tiles + CSS bars for now; ApexCharts wiring is a follow-up.
- Live bus refresh on `signed_off` (brief §7.1) — manual Refresh button for now.
- Pixel-level visual diff vs the prototype awaits the `/prototypes/` files.
