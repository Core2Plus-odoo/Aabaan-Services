# FM Asset

Asset registry for the FM Platform (brief §5.2). Depends on `fm_branding` and
the standard **Maintenance** app.

## Decision log (brief §2.2 — standard-first hierarchy)

| Model | Decision | Rationale |
|---|---|---|
| `fm.asset` | **Compose with `maintenance.equipment`** (`_name='fm.asset'` + `_inherit='maintenance.equipment'`) | Reuse the standard equipment fields/behaviour while exposing a distinct `fm.asset` model that every other `fm_*` module references as a Many2one target (hierarchy step 3). |
| `fm.asset.category` | **New model** | Service-line classification + PPM defaults have no Odoo precedent. Uses `_parent_store` for fast hierarchy queries. |
| `fm.asset.location` | **New model** | Site→Building→Floor→Zone→Room hierarchy with geo + area is FM-specific. |

## Deferred fields (added when their modules land)

To avoid forward dependencies, these brief §5.2 fields are intentionally not in
this module yet:

- `contract_id` → arrives with `fm_contract`
- `last_ppm_date` / `next_ppm_date` / `ppm_compliance_pct` → `fm_ppm`
- `mtbf_hours` / `mtbf_band` → computed from `fm_workorder` failure history
- `default_checklist_template_id` (category) / `required_skill_ids` → `fm_ppm` / `fm_workorder`
- `qr_code_image`, asset photo/document one2many → kept as `qr_code_data` (a URL)
  + standard chatter attachments for now; image generation added with the report layer.

## UI

Standard list/form/search + the FM application root menu (`menu_fm_root`) under
which later modules attach. The `assets.html` OWL stats hero (brief §7.5) is
deferred until the `/prototypes/` files are provided.

## Models

- `fm.asset.category` — name, service_line, criticality/PPM defaults, hierarchy.
- `fm.asset.location` — typed location hierarchy, `full_path`, geo, area.
- `fm.asset` — code (sequenced `AST-#####`), category, location, criticality,
  lifecycle state, identity, commercial fields, `qr_code_data`.
