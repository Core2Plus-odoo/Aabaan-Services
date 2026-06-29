# FM Platform — Odoo 19 Enterprise End-to-End Implementation Brief
**Document ID:** `C2P-FM-2026-BRIEF-001`
**Version:** 1.0
**Owner:** C2P Consultants FZC LLC (Official Odoo Partner)
**Prepared for:** Implementation team / AI coding agent
**Status:** Authoritative — supersedes prior FM Claude Code prompt

---

## 0. Executive Read (60 seconds)
You are an expert Odoo 19 Enterprise developer (or AI coding agent acting as one) delivering a **production-grade Facility Management ERP** for C2P Consultants — an Official Odoo Partner serving the GCC market. The product is a tenant-ready platform for FM service providers managing multi-building portfolios under AMC contracts.

The **UX has already been designed and prototyped** as seven HTML files in this repository's `/prototypes/` folder. Those prototypes are the **design source of truth** — every view, every interaction, every state transition must match the prototype's behavior in production Odoo.

You will:
1. Build the platform as **a suite of `fm_*` Odoo modules** depending on Enterprise standards where possible (Maintenance, Field Service, Stock, Sales, Accounting, Mail) and extending only where the standard falls short.
2. Implement the OWL 2 frontend components needed to render the prototype's dashboard, dispatch scheduler, work-order detail page, kanban list, and supporting pages — inside Odoo's web client.
3. Wire end-to-end workflows from work-order creation → dispatch → execution → customer sign-off → invoice generation → contract health update.
4. Deliver a multi-company, AED-default, VAT-5%-compliant, Arabic-ready system with role-based access for dispatcher, technician, manager, customer, and auditor.
5. Hand over with full test coverage, documentation, training materials, and a go-live runbook.

**Project duration:** 26–30 weeks across 9 phases.

**Definition of Done:** A new C2P customer can be onboarded in under 4 hours, the technician PWA works offline in a basement chiller room, and the executive dashboard updates within 5 seconds of a status change in the field.

---

## 1. Mission & Strategic Context

### 1.1 Business case
C2P Consultants serves the GCC FM market (UAE, Oman, KSA, Bahrain) — a sector dominated by aging custom-built CMMS systems (Maximo, Planon, MicroMain) or generic Odoo deployments that ignore FM-specific workflows. The opportunity is a **purpose-built FM ERP on the Odoo backbone**, sold as either:
- **SaaS** (multi-tenant via Odoo.sh) for SME FM contractors, AED 8,000–20,000/month.
- **Self-hosted Enterprise** for large portfolios (Emaar, Aldar, Majid Al Futtaim level), AED 250,000–800,000 one-time + AMC.

### 1.2 Product positioning
| Dimension | FM Platform | Maximo/SAP PM | Generic Odoo |
|---|---|---|---|
| Time to deploy | 4–8 weeks | 9–18 months | 8–12 weeks |
| Mobile-first | ✅ PWA-first | ❌ Desktop-first | ⚠️ Limited |
| FM-specific workflows | ✅ Out-of-box | ⚠️ Customization-heavy | ❌ Generic |
| GCC compliance | ✅ Civil Defence, DEWA, Municipality | ❌ Generic | ❌ Generic |
| Total cost over 5 years | Low | Very high | Medium |
| Customer portal | ✅ Native | ⚠️ Bolt-on | ⚠️ Generic |

### 1.3 Target customer profile
- **Primary:** FM contractors holding 5+ AMC contracts, 50–500 field staff, AED 10M–200M revenue
- **Secondary:** In-house FM teams of large building owners (commercial real estate, hospitality, retail)
- **Tertiary:** Government FM departments under Dubai Municipality, Civil Defence framework

---

## 2. The Four Non-Negotiable Constraints
Every decision in this implementation is governed by four constraints. If a proposed approach violates any of them, stop and escalate.

### 2.1 Odoo 19 Enterprise as host
- All custom code lives inside Odoo 19 Enterprise modules. No external services for core CRUD.
- Mobile is a PWA hosted by Odoo (`/web/` extended), not a separate React Native app.
- The web client is OWL 2 — no Vue, no React, no Angular.
- ApexCharts is the only third-party charting library (loaded via Odoo asset bundle).

### 2.2 Standard-first decision hierarchy
For any feature, walk this hierarchy. Stop at the first match:
1. **Use the Odoo Enterprise standard as-is** (e.g., `mail.thread` for comments).
2. **Extend the standard via inheritance** (`_inherit`) if the standard model lacks fields/methods.
3. **Compose with the standard** (e.g., `fm.workorder` `_inherits` from `maintenance.request`).
4. **Build new only if no standard exists** (e.g., `fm.contract.health.metric` — no Odoo precedent).

Document the decision in the module's `README.md` for every model.

### 2.3 `fm_*` namespace, never `c2p_*`
The platform is C2P's product but the modules are FM-generic and resellable. Module names: `fm_branding`, `fm_asset`, `fm_workorder`, `fm_ppm`, `fm_contract`, `fm_sla`, `fm_compliance`, `fm_dispatch`, `fm_mobile`, `fm_dashboards`, `fm_reports`, `fm_customer_portal`, `fm_integrations`.

Branding configuration is data-driven, not code-driven, so a future tenant can rebrand without forking the codebase. C2P logo, colors, and signature blocks load from `res.config.settings`.

### 2.4 UI fidelity to prototypes
The HTML prototypes in `/prototypes/` are not throwaway mockups. They are the **specification for OWL components**. Each prototype maps to one or more Odoo views as documented in §8. The visual design tokens (colors, fonts, spacing, shadows, radii) are reproduced in `fm_branding/static/src/scss/_tokens.scss` exactly as defined in the prototype `:root` blocks.

**Visual diff is a UAT criterion:** the final Odoo views must be visually indistinguishable from the prototypes at 1600px viewport, modulo the Odoo navbar.

---

## 3. Design Source of Truth — The Prototypes
The following prototype files exist and are authoritative. Place them in `/prototypes/` of the project repo. Treat them as the spec.

| Prototype file | Maps to | Notes |
|---|---|---|
| `dashboard.html` | Executive dashboard OWL component, accessible via menu "FM Operations / Executive Dashboard" | KPI tiles + revenue/SLA charts + at-risk contracts table + top performers |
| `dispatch.html` | Dispatch scheduler OWL component, menu "FM Operations / Dispatch Center" | Time-axis Gantt-style scheduler with drag-to-reassign + drawer + filter chips |
| `workorder.html` | Work Order form view (custom layout via OWL fields) | Stats strip + checklist + activity timeline + parts + sidebar cards + update-status modal wizard |
| `workorders.html` | Work Order kanban (custom view via OWL kanban renderer) | 6-column stage kanban + service-line color stripe + search |
| `assets.html` | Asset list with stats hero (custom OWL stats component above tree view) | Asset registry with criticality, MTBF, next PPM |
| `team.html` | Technician roster (OWL card view) | Card grid with utilization bars + CSAT |
| `reports.html` | Reports hub (OWL custom view) | Grouped report catalog with scheduling metadata |
| `data.js` | Reference data layer | The seed shape for `fm.workorder`, `fm.technician`, `fm.contract`. The localStorage layer disappears in Odoo — the ORM replaces it. |

### 3.1 Design tokens (from prototype `:root`)
```scss
// fm_branding/static/src/scss/_tokens.scss
:root {
  // Foundation
  --bg-page: #FAFAF7;
  --bg-canvas: #FFFFFF;
  --bg-subtle: #F5F5F1;
  --bg-muted: #EFEFE9;
  --bg-tint: #F9F8F4;
  // Ink scale (text)
  --ink-900: #1A1A1A; --ink-800: #2A2A2A; --ink-700: #3F3F3F;
  --ink-600: #5C5C5C; --ink-500: #7A7A7A; --ink-400: #999999;
  --ink-300: #BABABA; --ink-200: #DCDCD5; --ink-100: #ECECE6;
  // Borders
  --border-line: rgba(0,0,0,0.07);
  --border-soft: rgba(0,0,0,0.04);
  --border-strong: rgba(0,0,0,0.12);
  // Brand accent (deep forest green)
  --accent: #1F4434; --accent-deep: #0F2A1F;
  --accent-soft: #E8EFEA; --accent-tint: #F2F6F3;
  // Highlight (warm gold)
  --highlight: #B8923A; --highlight-soft: #FAF5E8;
  // Semantic
  --positive: #2E7D5F; --positive-soft: #E8F1EC;
  --warning: #C18A33; --warning-soft: #FAF1E4;
  --negative: #B83A3A; --negative-soft: #F9E9E9;
  --info: #3D6B8E; --info-soft: #EDF2F6;
  // Service-line colors
  --svc-hvac: #2C5F7C;        --svc-hvac-tint: #ECF1F5;
  --svc-electrical: #B8923A;  --svc-electrical-tint: #FAF5E8;
  --svc-plumbing: #3D7E8B;    --svc-plumbing-tint: #ECF3F4;
  --svc-cleaning: #6B5B95;    --svc-cleaning-tint: #F0EEF5;
  --svc-pest: #A05E5E;        --svc-pest-tint: #F5ECEC;
  --svc-security: #4A6B5E;    --svc-security-tint: #ECF1EE;
}
// Typography
$font-display: 'Instrument Serif', Georgia, serif;  // for KPI values, page titles
$font-sans: 'Inter', -apple-system, system-ui, sans-serif;
$font-mono: 'JetBrains Mono', 'SF Mono', Menlo, monospace;  // for IDs, timestamps, numbers
```
These tokens override Odoo's defaults via an asset bundle assigned to the FM backend (`web.assets_backend`). Do not modify Odoo's own scss.

> **Implementation note (amendment):** in `fm_branding` these tokens are namespaced as `--fm-*` (e.g. `--fm-bg-page`, `--fm-accent`, `--fm-svc-hvac`) to avoid collision with Odoo/Bootstrap custom properties in the shared backend scope. The mapping is 1:1 with the prototype names. See `addons/fm_branding/README.md`.

---

## 4. Module Architecture

### 4.1 Module dependency graph
```
fm_branding (foundation, theme, settings)
   │
   ├─ fm_asset (asset registry, hierarchy)
   │     └─ fm_compliance (regulatory regimes — depends on assets)
   │
   ├─ fm_workorder (work order core — depends on assets, contracts)
   │     ├─ fm_dispatch (scheduler — depends on workorder)
   │     ├─ fm_ppm (preventive maintenance — depends on workorder, assets)
   │     └─ fm_mobile (technician PWA — depends on workorder)
   │
   ├─ fm_contract (AMC contracts — depends on assets)
   │     └─ fm_sla (SLA rules & breach detection — depends on contract, workorder)
   │
   ├─ fm_dashboards (executive & operations dashboards)
   │
   ├─ fm_reports (operational/financial/compliance reports)
   │
   ├─ fm_customer_portal (customer-facing — depends on workorder, contract)
   │
   └─ fm_integrations (Mail, SMS, WhatsApp, BMS, payment, IoT)
```

### 4.2 Module skeletons
Every `fm_*` module follows the same structure:
```
fm_<name>/
├── __init__.py
├── __manifest__.py
├── README.md                    # Decision log: why this module exists, what's standard vs custom
├── models/
│   ├── __init__.py
│   └── <model files>
├── views/
│   ├── <model>_views.xml
│   ├── menus.xml
│   └── templates.xml
├── security/
│   ├── ir.model.access.csv
│   └── security.xml             # Groups, record rules
├── data/
│   ├── demo_<name>.xml
│   ├── ir_sequence.xml
│   └── ir_cron.xml
├── wizards/
│   ├── __init__.py
│   └── <wizard files>
├── reports/
│   ├── <report>_template.xml
│   └── <report>_action.xml
├── controllers/
│   ├── __init__.py
│   └── <controller files>       # For PWA, portal, API endpoints
├── static/
│   ├── src/
│   │   ├── components/          # OWL components
│   │   ├── scss/
│   │   └── xml/                 # OWL templates
│   └── description/             # Icon, index.html for app store
├── tests/
│   ├── __init__.py
│   ├── test_<feature>.py
│   └── common.py
└── i18n/
    ├── ar.po
    └── en.po
```

`__manifest__.py` template:
```python
{
    'name': 'FM <Module Display Name>',
    'version': '19.0.1.0.0',
    'category': 'Facility Management',
    'summary': '<one-line summary>',
    'description': '''<longer description>''',
    'author': 'C2P Consultants FZC LLC',
    'website': 'https://c2p.ae',
    'license': 'OPL-1',
    'depends': ['fm_branding', 'maintenance', '<other deps>'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/menus.xml',
        'views/<model>_views.xml',
        'reports/<report>_template.xml',
    ],
    'demo': ['data/demo_<name>.xml'],
    'assets': {
        'web.assets_backend': [
            'fm_<name>/static/src/scss/*.scss',
            'fm_<name>/static/src/components/**/*.js',
            'fm_<name>/static/src/components/**/*.xml',
        ],
    },
    'installable': True,
    'application': False,  # Only fm_branding is application=True
    'auto_install': False,
}
```

---

## 5. Data Models — Detailed Specifications
This section enumerates every model. Field types follow Odoo conventions. Defaults, computed fields, and constraints are explicit. (See the source brief for full field-by-field specs of `fm_branding`, `fm_asset`, `fm_workorder`, `fm_ppm`, `fm_contract`, `fm_sla`, `fm_compliance`, and the abbreviated models.)

Key rule: **stored fields > computed fields > related fields**, with explicit `tracking=True` for audit-critical fields.

---

## 6. State Machines & Business Logic
- **6.1 Work Order state machine:** draft → assigned → acknowledged → arrived → in_progress → completed → signed_off, with awaiting_parts / awaiting_customer side-branches and cancelled as a terminal state. Transitions enforced server-side via a single `action_stage_change(new_stage, **kwargs)` method.
- **6.2 SLA computation:** response = first acknowledgment − creation; resolution = signed_off − creation − paused minutes. Breach detection via `@api.depends` + a 5-minute cron.
- **6.3 Auto-dispatch algorithm:** skill/cert match are disqualifiers; score on proximity, utilization, history, CSAT.
- **6.4 WO → invoice automation:** break_fix bills per WO; amc_comprehensive logs to analytic; amc_non_comprehensive bills out-of-scope only. VAT 5%.
- **6.5 Contract health scoring:** 0–10 weighted on SLA, CSAT, open criticals, payment timeliness, qualitative score. Nightly cron + recompute on sign-off.
- **6.6 Compliance certificate watchdog:** daily 06:00 cron auto-creates compliance WOs ahead of expiry and escalates expired certs.

---

## 7. UI Components & Views — Prototype Mapping
Each prototype HTML file maps to OWL components / views (Executive Dashboard, Dispatch Center, Work Order form, Work Order kanban, Asset Registry, Technician Roster, Reports Hub) plus the Customer Portal (designed in Phase 5). See §7 of the source brief for per-component detail.

---

## 8. Security & Access Rights
FM role hierarchy (implemented in `fm_branding`): `group_fm_user` → `group_fm_technician` / `group_fm_dispatcher` → `group_fm_manager` → `group_fm_account_manager` → `group_fm_admin`; plus `group_fm_auditor` (read-only) and `group_fm_customer` (portal). Record rules scope technicians to their own WOs, account managers to their contracts, customers to their company, with multi-company rules throughout. Each model ships a comprehensive `ir.model.access.csv`.

---

## 9. Localization & Compliance — UAE/GCC Specifics
AED default + multi-currency; VAT 5% (UAE FTA) and ZATCA numbering for KSA; Mon–Sat working week with UAE holidays and Ramadan toggle; Arabic translations + RTL; regulatory regimes seeded per country (Civil Defence, DEWA, Dubai Municipality, TASNEEF, etc.); branded bilingual document standards.

---

## 10. Integrations
Email (fetchmail in, mail.template out), SMS (Twilio/Etisalat/Du via provider abstraction), WhatsApp Business API, BMS/SCADA connectors (Modbus/BACnet/MQTT), payment gateways (Stripe, Tabby, Network International), IoT webhook endpoint, customer SSO (SAML/OIDC), and S3-compatible attachment storage for large deployments.

---

## 11. Performance Requirements
95th-percentile targets: dashboard < 2.0s, WO list < 1.5s, WO form < 1.2s, scheduler < 2.5s, status commit < 800ms, PWA sync < 5s/20 actions, search across 100k WOs < 1.5s. Indexes on all state/relation fields + composite `(stage, technician_id, schedule_date_start)`; per-user chart caching; 60s dashboard KPI cache invalidated by bus events; optimistic locking for concurrency.

---

## 12. Testing Strategy
≥80% unit coverage; functional tests for every WO transition; integration tests for WO→invoice, PPM→WO, Compliance→WO; Playwright UI journey tests against the prototypes; locust performance tests. Demo data matches the prototype seed shape; CI fixtures scale to 100k WOs. 12 scripted UAT scenarios, pass criteria zero P1/P2 and CSAT ≥ 4/5.

---

## 13. Phase Plan & Deliverables
Phase 0 Discovery → 1 Foundation (`fm_branding`, `fm_asset`) → 2 `fm_workorder` core → 3 `fm_contract`/`fm_sla` → 4 `fm_dispatch`/kanban → 5 `fm_ppm`/`fm_compliance` → 6 `fm_mobile` PWA → 7 `fm_customer_portal` → 8 `fm_dashboards`/`fm_reports` → 9 Integrations & polish → 10 UAT/Training/Go-Live → 11 Hypercare. **Total ~32 weeks.**

---

## 14. Deployment
Odoo.sh for SaaS/SME; self-hosted AWS Bahrain / Azure UAE North for enterprise & data-residency. CI/CD (flake8, pylint-odoo, pytest, odoo-test-runner, Playwright) with staging auto-deploy and manual prod approval; migration scripts under `migrations/<version>/`. Daily backups + hourly WAL PITR, cross-region DR, RPO 1h / RTO 4h. Sentry + Datadog/Grafana + PagerDuty.

---

## 15. Documentation Deliverables
End-user guides per role + videos + in-app help; admin runbooks (4-hour tenant onboarding) + config/integration guides; developer ADRs, diagrams, API reference; classroom + train-the-trainer curricula with a certification quiz.

---

## 16. Acceptance Criteria — Definition of Done
Per-feature: merged + reviewed, unit + functional tests, UI matches prototype at 1600px, EN/AR translations, documented, permissions configured, `mail.thread` if audit-relevant, no Playwright regressions. Phase exit: all features DoD, successful demo, performance met, 0 P1/P2 & ≤5 P3, docs updated, sponsor sign-off (Muhammad Umer). Go-live: all phases passed, ≥95% UAT pass, prod load-tested, migration verified, cutover rehearsed, hypercare standby, ≥80% training attendance.

---

## 17. Out of Scope (Future Versions)
AI auto-dispatch optimization, predictive maintenance from IoT, voice-controlled PWA, AR/MR overlays, drone facade inspection, customer AI chatbot, parts marketplace, subcontractor portal, multi-trade work permits, real-time energy/carbon dashboard.

---

## 18. Risk Register
Odoo version drift, customer-driven customizations breaking upgrade path, PWA offline-sync conflicts, performance regressions, integration-partner outages, scope creep, Arabic RTL lib bugs, customer go-live readiness — each with mitigations (pin version, standard-first enforcement, optimistic locking, CI benchmarks, provider abstraction, locked phase scope, RTL QA, train-the-trainer + hypercare).

---

## 19. C2P-Specific Branding & Operational Notes
C2P logo at `/home/claude/c2p_logo.png`; primary red `#C8222A`; document reference pattern `C2P-[CLIENT]-[YEAR]-[TYPE]-[SEQ]`; PDF footer with trade licence `BC-890182`, 26th Floor Amber Gem Tower, Ajman, UAE. Delivery coordinator: Umar Farooq. Technical deployment lead: Shafat Ali (shafat.ali@core2plus.com). For SaaS tenants, `fm_branding` is configured per tenant while the codebase stays identical — critical for resale.

---

## 20. How to Begin
1. Clone the repo and verify the seven prototype files are in `/prototypes/`.
2. Read this brief and the prototypes side-by-side.
3. Provision a fresh Odoo 19 Enterprise instance.
4. Create `fm_branding` first — confirm the theme tokens override styling.
5. Build modules in §4.1 order, completing manifest/models/security/views/demo/tests per module.
6. Run the full test suite + Playwright journey tests after each module.
7. At each phase exit, demo to C2P and obtain written sign-off.
8. When in doubt, ask. The prototypes are the spec; escalate ambiguity before assuming.

---

## 21. Appendix A — Glossary
AMC, PPM, SLA, CSAT, ACV, TCV, MTBF, WO, OWL, PWA, DEWA, ZATCA — see source brief for definitions.

---

## 22. Appendix B — Module Sequence Diagram
Customer email → fetchmail → `fm.workorder.create()` → auto-assign → SMS → acknowledged → arrived (geofence) → in_progress → checklist + parts (stock.move) + labor → completed → customer sign-off + CSAT → signed_off → side effects (SLA eval, health recompute, invoice draft, MTBF recalc, dashboard bus push) → dispatcher sees real-time column move.

---

**End of brief.**

*This file is the repo copy of `C2P-FM-2026-BRIEF-001 v1.0`. Sections 5–7 are summarized here for length; the authoritative field-by-field model specs, UI component details, and full prose live in the originating brief and should be amended here via versioned updates (do not rewrite history). Prepared by C2P Consultants FZC LLC for internal and partner use.*
