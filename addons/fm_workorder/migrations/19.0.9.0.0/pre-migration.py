# -*- coding: utf-8 -*-
# Field Service re-base cleanup. The retired modules (fm_workorder / fm_ppm /
# fm_sla / fm_integrations) were replaced by native Field Service, but their old
# UI records linger in installed databases and reference fields/models that no
# longer exist. Odoo only purges them at end-of-load, so they break view
# revalidation / FKs when fm_fsm loads. This runs early (on upgrade to the empty
# stub) and removes the doomed crons/views/menus/actions. Idempotent.
import logging

_logger = logging.getLogger(__name__)

RETIRED_MODULES = ("fm_workorder", "fm_ppm", "fm_sla", "fm_integrations")
DEFUNCT_MODELS = (
    "fm.workorder",
    "fm.workorder.checklist.item",
    "fm.workorder.parts.line",
    "fm.workorder.labor.line",
    "fm.checklist.template",
    "fm.ppm.schedule",
)
UI_TABLES = (
    ("ir.ui.view", "ir_ui_view"),
    ("ir.ui.menu", "ir_ui_menu"),
    ("ir.actions.act_window", "ir_act_window"),
    ("ir.actions.client", "ir_act_client"),
    ("ir.actions.server", "ir_act_server"),
    ("ir.actions.report", "ir_act_report_xml"),
    ("ir.cron", "ir_cron"),
)


def _module_res_ids(cr, model):
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE model = %s AND module IN %s",
        (model, RETIRED_MODULES),
    )
    return [r[0] for r in cr.fetchall()]


def _delete_crons(cr):
    # ir.cron _inherits ir.actions.server via a FK, so crons go before actions.
    srv_ids = _module_res_ids(cr, "ir.actions.server")
    cron_ids = set(_module_res_ids(cr, "ir.cron"))
    if srv_ids:
        cr.execute("SELECT id FROM ir_cron WHERE ir_actions_server_id IN %s", (tuple(srv_ids),))
        cron_ids |= {r[0] for r in cr.fetchall()}
    if not cron_ids:
        return
    cron_ids = tuple(cron_ids)
    cr.execute("DELETE FROM ir_cron_trigger WHERE cron_id IN %s", (cron_ids,))
    cr.execute("DELETE FROM ir_cron WHERE id IN %s", (cron_ids,))
    _logger.info("Re-base cleanup: removed %s cron(s)", len(cron_ids))


def _delete_views(cr):
    # Views doomed because their model is gone, or a retired module created them.
    cr.execute(
        """
        SELECT v.id FROM ir_ui_view v
        WHERE v.model IN %s
           OR v.id IN (
               SELECT res_id FROM ir_model_data
               WHERE model = 'ir.ui.view' AND module IN %s
           )
        """,
        (DEFUNCT_MODELS, RETIRED_MODULES),
    )
    doomed = {r[0] for r in cr.fetchall()}
    if not doomed:
        return
    # Expand to the transitive closure of children: any view that inherits a
    # doomed view is itself stale and must be deleted too, or its inherit_id FK
    # would block deletion of the parent.
    while True:
        cr.execute(
            "SELECT id FROM ir_ui_view WHERE inherit_id IN %s AND id NOT IN %s",
            (tuple(doomed), tuple(doomed)),
        )
        extra = {r[0] for r in cr.fetchall()}
        if not extra:
            break
        doomed |= extra
    total = len(doomed)
    # Delete leaves first (no remaining view inherits them).
    remaining = set(doomed)
    while remaining:
        cr.execute(
            "SELECT id FROM ir_ui_view WHERE id IN %s "
            "AND id NOT IN (SELECT inherit_id FROM ir_ui_view WHERE inherit_id IN %s)",
            (tuple(remaining), tuple(remaining)),
        )
        batch = [r[0] for r in cr.fetchall()] or list(remaining)
        cr.execute("DELETE FROM ir_ui_view WHERE id IN %s", (tuple(batch),))
        remaining -= set(batch)
    _logger.info("Re-base cleanup: removed %s stale view(s)", total)


def _delete_by_module(cr, model, table):
    ids = _module_res_ids(cr, model)
    if ids:
        cr.execute("DELETE FROM %s WHERE id IN %%s" % table, (tuple(ids),))
        _logger.info("Re-base cleanup: removed %s %s record(s)", len(ids), model)


def migrate(cr, version):
    if not version:
        return
    menu_ids = _module_res_ids(cr, "ir.ui.menu")
    if menu_ids:
        cr.execute("UPDATE ir_ui_menu SET parent_id = NULL WHERE parent_id IN %s", (tuple(menu_ids),))
        cr.execute("DELETE FROM ir_ui_menu WHERE id IN %s", (tuple(menu_ids),))
    _delete_crons(cr)
    for model, table in (
        ("ir.actions.act_window", "ir_act_window"),
        ("ir.actions.client", "ir_act_client"),
        ("ir.actions.server", "ir_act_server"),
        ("ir.actions.report", "ir_act_report_xml"),
    ):
        _delete_by_module(cr, model, table)
    _delete_views(cr)
    # Remove dangling ir_model_data anchors for any UI record now gone.
    for model, table in UI_TABLES:
        cr.execute(
            "DELETE FROM ir_model_data d WHERE d.model = %s "
            "AND NOT EXISTS (SELECT 1 FROM {t} t WHERE t.id = d.res_id)".format(t=table),
            (model,),
        )
