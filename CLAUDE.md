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
| Scheduling / recurring visits | `project.task` | `fm_fsm` — **one** generator, `fm.visit.schedule.mixin`, driven from the contract (the `sale.order`). Confirming the order fills the horizon; the daily cron is shipped off |
| Calendar | native `calendar.event` on tasks | — |
| SLA | (native SLA policies to be configured) | SLA targets kept on `fm.sla.rule` (in `fm_contract`) |
| Contracts / AMC billing | **Sales** — the contract IS the `sale.order` — + **Subscriptions** (`sale.subscription`) | `fm_contract` adds FM fields to `sale.order`; `fm_subscription`. The old `fm.contract` model is frozen and being retired |
| Invoicing | native `account.move` (FTA tax invoice) | — |
| Assets | **Maintenance** (`maintenance.equipment`) | `fm.asset` |
| Compliance | Activities / Documents | `fm_compliance` regimes + certificates |
| Dashboards | native graph/pivot actions on the records themselves | **one** executive dashboard: `fm_command_centre`, its own app (OWL, seven tabs). The FM app carries no dashboards |

**Standard covers it — configure, don't code** (see
`docs/FM_LIFECYCLE_WORKFLOW.md`): checklists = **FSM Worksheet Templates**
(`industry_fsm_report`, Studio); materials used on a job + billing them =
**products on tasks** (`industry_fsm_sale` / `industry_fsm_stock`); job
time = native **timesheets** on the FSM task; contract e-signature = **Sign**;
files = chatter + **Documents** app; renewals/MRR = **Subscriptions**;
onboarding = Customer/CRM. Before adding any model, check this list and the
native FSM sub-apps first. Prefer extending an existing `fm_*` module over
creating a new one.

---

## 2. Module map (`addons/`)

**Active FM suite** (dependency order):

1. `fm_branding` — app root, company brand fields (name defaults "Aabaan
   Services"), currency/VAT, FM role groups (`res.groups.privilege` pattern),
   `--fm-*` design tokens. Only module with `application=True`.
2. `fm_asset` — `fm.asset` (inherits `maintenance.equipment`), categories,
   locations. Owns the FM app root menu `menu_fm_root`.
3. `fm_contract` — **the FM layer on `sale.order`** *(and on `crm.lead`:
   the Sales → Accounts → Operations handover, see §4)*: `is_fm_contract`, term,
   ACV/TCV, covered assets, inclusions/exclusions, `fm_lifecycle` (starts
   where `sale.order.state` stops), health, and the printed agreement wording
   (`fm.agreement.mixin`). Also `fm.sla.rule`, service items, penalties and
   the Customers menu. The legacy `fm.contract` model (`_inherits sale.order`)
   is frozen — nothing creates it, dependants are being re-pointed off it.
4. `fm_fsm` — **the re-base core**. FM Field Service project, task stages,
   FM fields on `project.task` (`fm_contract_order_id` → the contract's
   `sale.order`; legacy `fm_contract_id` kept until `fm.contract` goes),
   visit auto-scheduling in `fm.visit.schedule.mixin` — **the platform's
   only visit generator** — and `menu_fm_config_root`.
5. `fm_compliance` — `fm.compliance.regime` / `fm.compliance.certificate`,
   watchdog cron; remediation creates a `project.task`.
6. `fm_documents` — QWeb PDF layouts (Work Order job sheet, Contract,
   Compliance Certificate), bilingual EN/AR, TRN, QR.
7. `fm_branch` — `fm.branch` (emirate offices); `branch_id` on `fm.contract`
   and `project.task`; branch on `hr.employee` and PDFs.
8. `fm_reports` — OWL "Reports Hub" catalog of native actions.
8b. `fm_supervisor_dashboard` — the dispatcher's week board ("Maintenance
    Calendar"). An operational screen, not an executive dashboard; it stays
    in the FM app.
9. `fm_command_centre` — **the executive dashboard, and its own app**:
   seven tabs (overview, field ops, sales, finance, expenses, cash, AMC
   renewals), each loaded on demand. `application=True`, root menu
   `menu_command_centre_root`, gated by its own
   `group_command_centre_viewer` — it covers the whole business, not just
   FM, and is installable without the FM suite: `depends` is
   `project, sale_management, account, crm`, and every platform-specific
   field is resolved at runtime through `FIELD_ALIASES` (`fm_service_line`
   here, `x_service_line` on the `aabaan` build) / `COMPLIANCE_SOURCES`,
   with any section whose concept nothing answers collapsing itself.
   Deliberately does NOT depend on `aabaan_visit_schedule` — that is the
   second visit generator.
   **Replaced `fm_ceo_dashboard`, `fm_exec_dashboard` and `fm_dashboards`**,
   all three now retired to stubs (see §5).
9b. `aabaan_website_theme` — **the public website**: booking-first homepage
    at `/`, `/services` + four service pages with rate cards, `/about`,
    `/faq`, `/booking` -> `crm.lead`, branded footer and mobile action bar,
    brand SCSS (`#17171a` / `#ef7d25`). Maintained in the `aabaan` repo and
    ported here verbatim (same technical name) because an Odoo.sh project
    only loads its own addons path. **Supersedes `fm_website`**, whose four
    pages claim the same URLs; the theme's install hook parks any clashing
    page at `<url>-classic`, unpublished, so the two do not fight — but
    `fm_website` should be uninstalled from Apps and then deleted from
    source (see §5).
10. `fm_subscription` — recurring AMC billing on the **`sale.order`**:
    `product.template.fm_bills_as_subscription` opts a product in, and
    confirming a contract that sells one puts the order on the
    `sale.subscription.plan` matching its billing frequency. The
    `fm.contract` layer (the legacy **Start Subscription** button) is
    kept only until that model goes.
11. `fm_aabaan_config` — **seed data**: branches, service categories, UAE
    compliance regimes, service products. Makes the platform Aabaan-ready.

**Migration / one-off tools — DONE AND REMOVED.** `fm_aabaan_migration`
(legacy contract/visit → `fm.contract` + `project.task` wizard),
`fm_wo_migration` (leftover-`fm_workorder`-table → `project.task` SQL
converter) and `fm_data_import` (XML-RPC master-data importer, whose
pre-migration also **dropped the `odoo_master_data_config` table** and with
it the stored source API keys) each ran their `19.0.9.0.0` pre-migration on
the production upgrade, were uninstalled from Apps, and have been deleted
from source per §5.

**Retired stubs — awaiting uninstall.** `fm_ceo_dashboard`,
`fm_exec_dashboard` and `fm_dashboards` — three dashboards under one app
root, two of them named "CEO Dashboard", all superseded by the Command
Centre. Each is now an empty `19.0.9.0.0` stub with a pre-migration (§5);
uninstall them from Apps once the production upgrade has run, then delete
the stubs from source. `fm_exec_dashboard`'s two *stored* fields were not
dashboard code and moved to `fm_branch`, which owns them:
`account.move.branch_id` and `fm.branch.monthly_revenue_target` — columns
and data untouched.

**Retired stubs — removed.** `fm_workorder`, `fm_ppm`, `fm_sla`,
`fm_integrations` were empty placeholder modules that existed only so an
installed DB loaded cleanly while their residual DB records were purged (by each
stub's `migrations/19.0.9.0.0/pre-migration.py`, see §5). They have been
**uninstalled on production and deleted from the repo**.

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
  actions on the records themselves — the FM Work Orders action already
  carries `pivot` and `graph` views, which is why a separate "Operations
  Dashboard" action was pure duplication.
- **Re-declaring a `<menuitem>` without a `parent` attribute RESETS
  `parent_id` to False** (`_tag_menuitem` starts from `{'parent_id': False}`)
  — the menu detaches and floats to the root. When re-sequencing another
  module's menu, always repeat `parent=` (see `fm_fsm/views/menus.xml`).
- **Computed stored `Monetary` fields need an explicit `aggregator="sum"`** to
  be usable as pivot/graph measures (else `No aggregate function has been
  provided for the measure`), and their `currency_field` should be stored.
- **`project.task.date_deadline` must be `>= planned_date_begin`** (a server
  constraint) — don't set `date_deadline` to midnight-of-day while
  `planned_date_begin` is later that same day, or `create()` raises "planned
  start date must be before planned end date". Use the visit's *end* instant
  for `date_deadline`, not the bare day.
- **`project.task.date_end` is silently discarded when passed inside
  `create()`** on this build (verified live) — it comes back `False` even
  though the field is stored/writable. A `write()` immediately after `create()`
  is the only way it sticks. `planned_date_begin` and `allocated_hours` persist
  fine on `create()`. See
  `fm_fsm/models/fm_visit_schedule_mixin.py::_generate_schedule`.
- **Extending an `AbstractModel` only reaches models built *before* the
  extension is registered.** A model composes its class from the abstract
  models it inherits at build time, so extending a mixin from a later module
  does NOT retro-fit models that already inherited it — no error is raised,
  the behaviour just never runs. Either declare the concrete models in the
  same module, importing the mixin file first (see `fm_branch/models/`), or
  just write a plain `_inherit` extension on each concrete model and share
  the body through a module-level function (see
  `fm_service_materials/models/fm_visit_schedule_mixin.py`).
- **A monthly cadence is a calendar step, not `365/12` days.** Visit
  recurrence lives in `fm_fsm/models/fm_visit_schedule_mixin.py`
  (`FREQUENCY_MONTHS` / `_fm_visit_dates`). Stepping by `round(365/12)=30`
  days drifts: a contract signed for the 19th lands on the 18th by visit 3
  and the 15th by visit 12 — silently, on every recurring contract. The
  monthly family (monthly, bi-monthly, quarterly, semi-annual, annual) steps
  by whole months, **anchored on the contract start** so a short month does
  not drag later ones back (31 Jan → 28 Feb → **31** Mar). Weekly and
  fortnightly stay day-based, because months do not preserve weekdays.
  Client requirement: *"A job created for 19-Sep-2026 on a monthly frequency
  must reflect on the 19th of every following month."*
  **Still unconfirmed by the client** (their process document lists these as
  open): the exact date spacing for an "8 times / year" plan, whether
  "twice a month" means two fixed dates or a 14-day step, and what happens
  to future visits when a contract is renewed, paused or cancelled. Short
  months clamp to the last day, which that document suggests but does not
  confirm.
- **The time slot on a visit is derived, not stored twice.**
  `project.task.fm_time_slot` (Morning / Day / Night) is a stored compute off
  `planned_date_begin` — so a job dragged to another slot on the Gantt, or
  created by hand, is always tagged correctly and no tag can go stale. The
  contract picks a slot, which fills in `visit_start_time`; the *time* stays
  the single source of truth and the slot is the label. Start times
  (08:00 / 13:00 / 21:00) come from the client's technician screen; the
  **boundaries between slots are ours** — under 12:00 morning, under 18:00
  day, otherwise night — because that document names the slots and their
  start times but never where one ends. **Also unconfirmed:**
  `planned_date_begin` is a UTC Datetime while the generator writes
  `visit_start_time` into it as a wall clock, so both sides currently share
  that one interpretation. Correcting it is a separate change — it would
  move every already-planned visit by the UTC offset.
- **A computed field with no `store=` cannot be searched** without an
  explicit `search="_search_..."` method — the field renders fine in a list
  and then the first filter using it fails at runtime, not at parse time.
  See `project.task.fm_has_service_document`, which backs the "Awaiting
  Documents" filter.
- **The service-document gate is a flag on the stage, not a stage id.**
  `project.task.type.fm_requires_document` marks Completed and Signed Off;
  `project.task.write()` refuses to enter any flagged stage while nothing is
  attached to the visit. Enforced in `write()` rather than the view so it
  holds for kanban drag, form, mobile app, import and RPC alike — the client
  requires it "enforced in the system logic, not optional for any user
  role". Note `data/fsm_stages.xml` is `noupdate="1"`, so the flag and the
  re-sequencing around the new **Pending Documents** stage had to be applied
  to existing databases by `migrations/19.0.2.8.0` — shipping them in the
  data file alone would have left the gate doing nothing on exactly the
  databases that have real visits.
- **The Accounts → Operations gate is a constraint, not a button check.**
  The client's process flow says Operations confirmation is *"allowed only
  after Accounts confirmation"*. `crm.lead` carries three dated, attributed
  confirmations (`fm_sales_qualified_*`, `fm_accounts_confirmed_*`,
  `fm_ops_confirmed_*`) and `_check_fm_confirmation_order` enforces the
  ordering — so the rule also holds for import, RPC and server actions, and
  catches the reverse hole of *clearing* the Accounts date under a lead
  Operations already confirmed. The buttons only supply the friendly
  message. Modelled as confirmations rather than CRM stages because the
  handover is not a single ordered list: step 2 drips the qualified lead to
  Accounts **and** Operations at once, and only then does the ordering
  between those two apply. **Still unconfirmed by the client:** which users
  are "Accounts" and which are "Operations" — the ordering is enforced for
  everyone, but no role restriction is applied, because that is their org
  chart to define, not ours.
- **The FM app lists contracts by `sale.order.is_fm_contract`, so nothing
  may depend on a human remembering to tick it.** An AMC is written and
  agreed in Sales; if the tick is left to whoever raised the quotation, a
  confirmed contract is invisible to Operations — no visit schedule, no
  renewal, nothing under FM → Contracts, and no error anywhere. So
  `fm_contract`'s `action_confirm` recognises the order first
  (`_fm_autodetect_contracts`): a product flagged
  `product.template.fm_is_contract_service`, a subscription plan, an FM
  service line, a contract term or covered assets each make it a contract,
  and the reason plus any derived term is posted to the chatter — a
  contract that appeared in the FM app on its own has to be able to say
  what made it one. The recognition runs **before** `super()` so that
  `fm_fsm`'s visit generation, which happens after its own `super()`
  returns, sees an order already marked. An order showing none of those
  signals stays an ordinary sale.
- **A subscription plan must be on the order *before* `super().action_confirm()`.**
  Odoo's own `_action_confirm` is what hands a recurring order to the
  subscription engine, so a plan written afterwards leaves an ordinary
  confirmed sale that happens to name a plan and bills nobody.
  `fm_subscription` therefore sets it from the outermost layer of the
  chain (it loads after `fm_contract` and `fm_fsm`, so it is first in the
  `sale.order` MRO). Opt-in is per product,
  `product.template.fm_bills_as_subscription`, which also switches Odoo's
  own `recurring_invoice` on — a subscription order needs one recurring
  product or confirmation is refused, and that belongs at product setup,
  not in the middle of confirming a customer's order. It is only ever
  switched *on*: a product can be recurring for reasons that have nothing
  to do with FM. **Why this existed at all:** `fm_subscription` was
  entirely on `fm.contract`, a frozen model nothing creates, reached
  through an admin-only "Contracts (legacy)" menu — so every AMC written
  as a `sale.order` had no way to bill recurrently, silently.
- **A restrictive `ir.rule` must be GLOBAL, or it restricts nothing.**
  Odoo OR-s together the rules of every group a user belongs to and AND-s
  the global ones (`ir_rule._compute_domain`). A technician is also a
  project user, and `project`'s own group rule lets a project user read
  the project's tasks — so a group-scoped rule limiting technicians to
  their own visits would simply be OR-ed with that one and change
  nothing. `fm_fsm/security/security.xml` therefore declares no `groups`
  at all (`global` is computed from `not groups`, so it must not be set
  by hand) and switches on `user.has_group(...)` inside `domain_force`,
  which is evaluated with the `res.users` record in scope. The trap is
  that the naive version *looks* right and a test asserting "the
  technician sees their own job" passes against it — only a test for the
  job they must **not** see catches it.
- **NEVER mix a plain Python class into a model's bases** —
  `class SaleOrder(SomePlainClass, models.Model)` — even though it looks like
  the tidy way to share a method across two models. A plain class carries an
  `object` instance layout, and when the registry rebuilds the model with
  `model_cls.__bases__ = model_cls._base_classes__` Python refuses:
  `TypeError: __bases__ assignment: 'SaleOrder' object layout differs from
  'SaleOrder'`. **The registry then fails to load and the database will not
  start.** This took production down on the #96 upgrade. Nothing local
  catches it: `py_compile` passes, XML parses, and it only fires when the
  registry is assembled — so a *dev* build that fails earlier (e.g. on demo
  data) will never reach it either. Any class listed in a model's bases must
  itself derive from `models.Model` / `models.AbstractModel`.

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
3. Verify **FM → Work Orders** and the **Command Centre** app.
4. Uninstall the retired dashboard stubs (`fm_ceo_dashboard`,
   `fm_exec_dashboard`, `fm_dashboards`) from Apps once their
   pre-migrations have run, then delete the stubs from source.

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
