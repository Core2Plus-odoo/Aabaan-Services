# Aabaan Services — FM Platform (Odoo 19 Enterprise)

Knowledge base and working guide for this repository. Read this first.

---

## 1. What this is

A **Facility Management (FM) platform for Aabaan Services** (UAE), built on
**Odoo 19 Enterprise** and deployed on **Odoo.sh** (production branch `main`,
instance `core2plus-odoo-aabaan-services.odoo.com`).

The platform is **standard-first**: it uses native Odoo apps as the engine and
adds only thin `fm_*` layers by `_inherit`. Data lives in native tables; the FM
app is a single cockpit that operates them.

| Capability | Native engine used | FM layer |
|---|---|---|
| Work orders | **Field Service** (`industry_fsm`, `project.task`, `is_fsm`) | `fm_fsm` adds asset/contract/severity/type fields + stages |
| Scheduling / recurring visits | `project.task` + daily cron | `fm_fsm` contract-driven `_generate_schedule` |
| Calendar | native `calendar.event` on tasks | — |
| SLA | (native SLA policies to be configured) | SLA targets kept on `fm.sla.rule` (in `fm_contract`) |
| Contracts / AMC billing | **Sales** + **Subscriptions** (`sale.subscription`) | `fm.contract` `_inherits sale.order`; `fm_subscription` |
| Invoicing | native `account.move` (FTA tax invoice) | — |
| Assets | **Maintenance** (`maintenance.equipment`) | `fm.asset` |
| Compliance | Activities / Documents | `fm_compliance` regimes + certificates |
| Dashboards | native graph/pivot actions | `fm_dashboards` (JS-free) |

---

## 2. Module map (`addons/`)

**Active FM suite** (dependency order):

1. `fm_branding` — app root, company brand fields (name defaults "Aabaan
   Services"), currency/VAT, FM role groups (`res.groups.privilege` pattern),
   `--fm-*` design tokens. Only module with `application=True`.
2. `fm_asset` — `fm.asset` (inherits `maintenance.equipment`), categories,
   locations. Owns the FM app root menu `menu_fm_root`.
3. `fm_contract` — `fm.contract` (`_inherits sale.order`), `fm.sla.rule`,
   service items, penalties, contract health. Customers menu.
4. `fm_fsm` — **the re-base core**. FM Field Service project, task stages,
   FM fields on `project.task`, contract-driven visit auto-scheduling + cron,
   `menu_fm_config_root`.
5. `fm_compliance` — `fm.compliance.regime` / `fm.compliance.certificate`,
   watchdog cron; remediation creates a `project.task`.
6. `fm_documents` — QWeb PDF layouts (Work Order job sheet, Contract,
   Compliance Certificate), bilingual EN/AR, TRN, QR.
7. `fm_branch` — `fm.branch` (emirate offices); `branch_id` on `fm.contract`
   and `project.task`; branch on `hr.employee` and PDFs.
8. `fm_dashboards` — native Operations & Contracts graph/pivot dashboards.
9. `fm_reports` — OWL "Reports Hub" catalog of native actions.
10. `fm_subscription` — bills `fm.contract` via `sale.subscription`.
11. `fm_aabaan_config` — **seed data**: branches, service categories, UAE
    compliance regimes, service products. Makes the platform Aabaan-ready.

**Migration / one-off tools:**

- `fm_aabaan_migration` — wizard: `aabaan.service.contract/visit` → `fm.contract`
  + `project.task`. Idempotent (`aabaan_contract_id` / `aabaan_visit_id`).
- `fm_wo_migration` — one-off converter: leftover `fm_workorder` **table** rows
  → `project.task` (reads by SQL; run before uninstalling the stubs).

**Retired stubs** — `fm_workorder`, `fm_ppm`, `fm_sla`, `fm_integrations`:
empty placeholder modules (`depends: base`, no models/data, `v19.0.9.0.0`).
They exist so an installed DB loads cleanly and can be uninstalled from Apps.
Each carries a `migrations/19.0.9.0.0/pre-migration.py` that purges the old
modules' crons/actions/views (see §5). **Do not build on these.** Once
uninstalled on production and confirmed, they and `fm_wo_migration` can be
deleted from the repo.

**Legacy:** `aabaan_service_scheduler` — the original pest/water-tank scheduler.
Hidden (root menus `active=False`), data preserved, superseded by the FM suite.

---

## 3. History: the Field Service re-base

The FM work order / PPM / SLA / calendar functionality was originally custom
(`fm_workorder` state machine, `fm_ppm`, `fm_sla`, `fm_integrations`). It was
**re-based onto native Odoo Field Service** because `industry_fsm` and
`sale_subscription` were already installed. The custom engines were retired to
empty stubs and every dependent re-pointed onto `project.task`. Existing data
is migrated by `fm_wo_migration` / `fm_aabaan_migration`.

---

## 4. Odoo 19 gotchas learned here (avoid re-hitting)

- **`res.groups` has no `category_id`** → use `res.groups.privilege` +
  `privilege_id`.
- **`ir.actions.act_window` `target="inline"` removed.**
- **`<group>` wrapper inside `<search>` rejected** → put group-by `<filter>`s
  directly under `<search>`.
- **Kanban `<t t-name="kanban-box">` renamed to `<t t-name="card">`.**
- **`name_get` → `_compute_display_name`; `read_group` → `_read_group`.**
- **`_sql_constraints` deprecated** → use class-level
  `models.Constraint("<sql>", "<message>")`.
- **Field params `unaccent=` (on Char) and `auto_join=` are rejected** → remove.
- **FSM projects require `company_id`** — a `project.project` with `is_fsm=True`
  must set `company_id` (check constraint
  `project_project_company_id_required_for_fsm_project`). See
  `fm_fsm/data/fsm_project.xml` (`company_id` = `base.main_company`).
- **`%(xmlid)d` interpolation works in an action's `domain` but NOT its
  `context`.** For a context default, bake the id in via a post-load
  `ir.actions.act_window.write` (see `fm_fsm/views/menus.xml`).
- **OWL client-action dashboards are fragile on stale asset bundles**
  (`KeyNotFound in actions registry`). Prefer native graph/pivot `act_window`
  actions (see `fm_dashboards`).

---

## 5. Deleting an installed module safely (Odoo.sh)

Removing a module's source while it is still installed on the DB breaks the
build (`Some modules are not loaded…`). Never delete-from-source an installed
module directly. Instead:

1. Replace it with an **empty stub** (`depends: base`, no data) so it still
   loads, and **bump its version** to force an upgrade.
2. Add a **`pre-migration.py`** that removes its residual DB records in
   FK-safe order: **crons → their server actions → other actions → views
   (transitive closure of `inherit_id` children, leaves first) → dangling
   `ir_model_data` anchors.** (See any retired stub's migration — this order
   was hard-won from cascading FK failures.)
3. Deploy, let the migration run, then **uninstall** the stub from Apps.

---

## 6. Deploy runbook (production)

1. Merge to `main` → Odoo.sh builds & upgrades.
2. If migrating legacy data: **FM → Configuration → Convert Legacy Work Orders**
   (once), then **Migrate Aabaan Data**.
3. Verify **FM → Work Orders / Dashboards**.
4. Uninstall the four retired stubs from Apps once verified.

**Odoo.sh builds:** dev-branch builds do a **fresh install** (migrations do NOT
run); **production does an upgrade** (migrations DO run). A green dev build does
not prove the production upgrade — always check the production `update.log`.

---

## 7. Workflow conventions

- Develop on branch **`claude/audit-4hgbif`**; open a PR to `main`; merge on
  request. After a squash-merge the branch diverges — **re-base it onto
  `origin/main` and re-apply only the delta** before the next PR.
- One change per PR; bump the touched module's `version` so Odoo upgrades it.
- Validate before pushing: `python3 -m py_compile` and XML parse.
- Commit trailers: `Co-Authored-By:` + `Claude-Session:` (never put the model
  id in commits/PRs).

---

## 8. See also

- `docs/UAE_FM_KNOWLEDGE.md` — UAE facility-management domain knowledge.
- `docs/IMPLEMENTATION_BRIEF.md` — original platform brief.
- `docs/FM_GETTING_STARTED.md` — user getting-started.
- `docs/deployment_notes.md`, `docs/import_mapping.md`.
