# FM Platform — Getting Started

How to use the FM Platform backend that is live today. Everything runs in the
standard Odoo backend; the branded OWL dashboards / dispatch / PWA screens
(brief §7) are not built yet — they depend on the `/prototypes/` files.

Modules live: `fm_branding`, `fm_asset`, `fm_contract`, `fm_workorder`,
`fm_ppm`, `fm_compliance`.

## 1. Install
**Apps → ⋮ → Update Apps List**, then install **FM PPM** and **FM Compliance**.
The dependency chain pulls in everything else
(`fm_workorder → fm_contract → fm_asset → fm_branding`) plus the standard
**Maintenance, Sales, Accounting** apps. Installing only *FM Branding* gives
just the foundation.

> Install in **demo mode** to get the sample dataset (a site, assets, a
> contract, work orders) described in §8.

## 2. Assign roles
**Settings → Users & Companies → Users →** your user → **Facility Management =
FM Administrator** to see all menus. Role hierarchy (brief §8.1):
User → Technician / Dispatcher → Manager → Account Manager → Admin, plus
Auditor (read-only) and Customer (portal).

## 3. Configure branding
**Settings → FM Platform** — brand name, logo, primary/accent colours, default
currency (AED), VAT %, compliance country. Stored per company.

## 4. Build core data (in order)
Under the **Facility Management** app menu:
1. **Configuration → Checklist Templates** — reusable inspection lists; mark
   items mandatory / photo-required.
2. **Assets → Categories** — service-line classification (HVAC, electrical…)
   with default criticality / PPM cadence.
3. **Assets → Locations** — create a *Site*, then *Building/Floor/Zone/Room*
   beneath it; the `full_path` breadcrumb builds automatically.
4. **Assets → Assets** — auto-numbered `AST-#####`; set category, location,
   criticality, lifecycle state.
5. **Contracts → Contracts** — customer + term (auto-numbers `AMC-####` and
   creates the linked sale order). Add **SLA Rules** (per-severity response /
   resolution targets), penalties, and tick **covered assets**. Click
   **Activate**.

## 5. Work-order lifecycle (brief §6.1)
**Operations → Work Orders → New**: asset + customer + contract + severity +
problem. Save → `WO-####`. Choose a checklist template (items populate).
Walk the header buttons:

```
Assign → Acknowledge → Arrived → Start → Mark Complete → Sign Off
                                   ↘ Awaiting Parts / Awaiting Customer ↗
```

Guards enforced server-side:
- **Mark Complete** is blocked until every *mandatory* checklist item is ticked.
- **Sign Off** requires a signature image **and** a CSAT rating.
- Awaiting-* pauses the SLA clock; resuming logs the paused minutes.

Add **Parts** and **Labor** lines on their tabs — totals roll up. The kanban
view groups by stage.

## 6. Preventive maintenance
**Operations → PPM Schedules** — asset + checklist + frequency (time/meter).
`next_due` computes automatically. The daily cron **FM: Generate PPM Work
Orders** raises a WO `wo_lead_days` before due. To test immediately:
**Settings → Technical → Scheduled Actions →** *FM: Generate PPM Work Orders* →
**Run Manually**.

## 7. Compliance
**Compliance → Regimes** (authority, applicable categories, task templates),
then **Compliance → Certificates** (asset + expiry date). The daily **FM:
Compliance Certificate Watchdog** raises a `compliance` work order when a
certificate is within 30 days of expiry, and flips expired certs to *expired*.
Run it manually the same way for testing.

## 8. Sample data (demo mode)
Installing in demo mode seeds: one site + building, an HVAC category, two
assets, a checklist template, one active AMC contract with a P1 SLA rule, and
two work orders (one reactive, one in progress). Use it to explore the flows
above without data entry.

## 9. Not built yet
- **`fm_sla`** — SLA breach detection, contract health scoring (§6.5),
  WO → invoice (§6.4).
- **OWL UI / integrations** — executive dashboard, dispatch scheduler,
  technician PWA, customer portal, reports hub, integrations
  (`fm_dispatch`, `fm_mobile`, `fm_dashboards`, `fm_reports`,
  `fm_customer_portal`, `fm_integrations`) — gated on the `/prototypes/` files.
