# FM Branding

Foundation module for the C2P Facility Management platform. See
[`docs/IMPLEMENTATION_BRIEF.md`](../../docs/IMPLEMENTATION_BRIEF.md) for the full
program brief — this module delivers the Phase 1 foundation (brief §13).

## What this module provides

1. **Branding configuration** (brief §2.3, §5.1) — logo, primary/accent colours,
   default currency, default VAT %, and compliance country, stored **per company**
   so each C2P-hosted tenant can rebrand without forking the codebase.
2. **Design tokens** (brief §2.4, §3.1) — the prototype `:root` palette and
   typography stacks, applied to the Odoo backend via `web.assets_backend`.
3. **FM security groups** (brief §8.1) — the role hierarchy every other `fm_*`
   module assigns access and record rules to.

This is the only `fm_*` module with `application=True`; all others depend on it.

## Decision log (brief §2.2 — standard-first hierarchy)

| Concern | Decision | Rationale |
|---|---|---|
| Branding storage | **Extend `res.company`** + relate on `res.config.settings` | Branding is per-company/per-tenant; this is the standard Odoo settings pattern (hierarchy step 2: extend the standard). No new model needed. |
| Settings UI | **Inherit `base_setup.res_config_settings_view_form`** | Reuse the standard Settings app shell rather than a bespoke screen. |
| Security roles | **New `res.groups`** under a new module category | No Odoo precedent for the FM role hierarchy (hierarchy step 4: build new). Groups imply `base.group_user` / `base.group_portal` so they compose with standard ACLs. |
| Design tokens | **New SCSS partial** loaded into `web.assets_backend` | No standard equivalent; required for prototype fidelity. Odoo's own SCSS is never modified (brief §2.4). |

### CSS variable naming

The prototype `:root` uses bare names (`--bg-page`, `--accent`, `--svc-hvac`…).
This module namespaces them as `--fm-*` (`--fm-bg-page`, `--fm-accent`,
`--fm-svc-hvac`…) to guarantee no collision with Odoo/Bootstrap custom
properties in the shared backend scope. Future `fm_*` OWL components consume the
`--fm-*` names; the mapping is 1:1 with the prototype tokens.

## Models

- `res.company` (extended) — `fm_brand_name`, `fm_brand_logo`,
  `fm_brand_color_primary`, `fm_brand_color_accent`, `fm_default_currency_id`,
  `fm_default_vat_rate`, `fm_compliance_country`.
- `res.config.settings` (extended) — related fields surfacing the above under
  **Settings → FM Platform**.

## Security groups

`group_fm_user` → `group_fm_technician`, `group_fm_dispatcher`
→ `group_fm_manager` → `group_fm_account_manager` → `group_fm_admin`;
plus `group_fm_auditor` (read-only) and `group_fm_customer` (portal).
