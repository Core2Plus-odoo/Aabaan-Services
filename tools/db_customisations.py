# -*- coding: utf-8 -*-
"""What is customised on the database that no module in this repo declares.

Run it in an Odoo shell on the target instance:

    odoo-bin shell -d <database> --no-http < tools/db_customisations.py

Why this exists. Three separate problems in one day came from the same
blind spot -- behaviour living in the database rather than in source:

* The standard Quotation / Order PDF was dead across the whole
  database because a module from the *other* Odoo.sh project had
  redirected ``sale.action_report_saleorder`` at its own template.
  That module is not on this addons path, so nothing in the repo could
  show it; it surfaced only when someone pressed Print.
* ``x_visit_frequency`` shadows fm_fsm's ``visit_frequency`` on
  ``sale.order`` under the same label -- a manual field no module here
  declares.
* Confirming a contract is blocked by a rule that prints "N highlighted
  field(s) in the agreement terms still need completing". That message
  exists in neither repository, so it is an automation or server action
  someone built on the database.

None of these are visible from a git checkout. This lists them.

Nothing here writes. It is safe to run on production.
"""
import logging

_logger = logging.getLogger(__name__)

try:
    env  # noqa: F821 -- supplied by the Odoo shell
except NameError:  # pragma: no cover - only when run outside the shell
    raise SystemExit(
        "Run this inside an Odoo shell:\n"
        "    odoo-bin shell -d <database> --no-http < tools/db_customisations.py"
    )


def _owner_module(env, model, ids):
    """{record id: module} from ir.model.data; absent means nothing owns it."""
    if not ids:
        return {}
    rows = env["ir.model.data"].sudo().search_read(
        [("model", "=", model), ("res_id", "in", list(ids))], ["res_id", "module"]
    )
    return {r["res_id"]: r["module"] for r in rows}


def _section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# ----------------------------------------------------------------------
# 1. Manual fields -- Studio or hand-made, with a real column behind them
# ----------------------------------------------------------------------
_section("MANUAL FIELDS (state = manual): schema no module declares")
manual = env["ir.model.fields"].sudo().search([("state", "=", "manual")], order="model, name")
if not manual:
    print("  none")
by_model = {}
for f in manual:
    by_model.setdefault(f.model, []).append(f)
for model, fields_ in sorted(by_model.items()):
    print("\n  %s" % model)
    # A label shared with a module field is how the wrong box gets filled in.
    labels = {}
    for other in env["ir.model.fields"].sudo().search(
            [("model", "=", model), ("state", "=", "base")]):
        labels.setdefault(other.field_description, []).append(other.name)
    for f in fields_:
        clash = labels.get(f.field_description)
        note = "  <-- SAME LABEL AS %s" % ", ".join(clash) if clash else ""
        print("    %-28s %-16s %r%s" % (f.name, f.ttype, f.field_description, note))

# ----------------------------------------------------------------------
# 2. Automations and server actions -- where a surprise rule usually lives
# ----------------------------------------------------------------------
_section("AUTOMATION RULES")
if "base.automation" in env:
    autos = env["base.automation"].sudo().with_context(active_test=False).search([])
    owners = _owner_module(env, "base.automation", autos.ids)
    if not autos:
        print("  none")
    for a in autos:
        print("  [%s] %-42s model=%-28s owner=%s"
              % ("on " if a.active else "off", a.name, a.model_id.model,
                 owners.get(a.id, "** none (built on the database) **")))
else:
    print("  base_automation is not installed")

_section("SERVER ACTIONS no module owns")
actions = env["ir.actions.server"].sudo().search([])
owners = _owner_module(env, "ir.actions.server", actions.ids)
orphans = [a for a in actions if a.id not in owners]
if not orphans:
    print("  none")
for a in orphans:
    print("  %-46s model=%-28s state=%s" % (a.name, a.model_id.model, a.state))

# ----------------------------------------------------------------------
# 3. Reports pointing at a template that does not exist
#    -- exactly the failure that killed the Quotation PDF
# ----------------------------------------------------------------------
_section("REPORTS whose template is missing (they raise on Print)")
broken = []
for report in env["ir.actions.report"].sudo().search([]):
    if not report.report_name:
        continue
    if not env.ref(report.report_name, raise_if_not_found=False):
        broken.append(report)
if not broken:
    print("  none -- every report action resolves to a template")
for report in broken:
    print("  %-34s model=%-22s report_name=%s"
          % (report.name, report.model, report.report_name))

# ----------------------------------------------------------------------
# 4. Views edited or created on the database (Studio leaves these behind)
# ----------------------------------------------------------------------
_section("VIEWS no module owns (Studio edits and hand-made views)")
views = env["ir.ui.view"].sudo().with_context(active_test=False).search([])
owners = _owner_module(env, "ir.ui.view", views.ids)
orphans = [v for v in views if v.id not in owners]
if not orphans:
    print("  none")
for v in orphans[:80]:
    print("  %-52s model=%s" % (v.name or "(unnamed)", v.model))
if len(orphans) > 80:
    print("  ... and %d more" % (len(orphans) - 80))

# ----------------------------------------------------------------------
# 5. Apps rows with no source on the addons path
#    -- these are what jam "another module operation is in progress"
# ----------------------------------------------------------------------
_section("MODULES in Apps with no source (orphan ir_module_module rows)")
orphan_modules = env["ir.module.module"].sudo().search([("latest_version", "=", False)])
installed_orphans = orphan_modules.filtered(lambda m: m.state not in ("uninstalled", "uninstallable"))
if not installed_orphans:
    print("  none")
for m in installed_orphans:
    print("  %-38s state=%s" % (m.name, m.state))

print("\nDone. Nothing was written.\n")
