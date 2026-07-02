# -*- coding: utf-8 -*-
# Field Service re-base cleanup. The retired modules (fm_workorder / fm_ppm /
# fm_sla / fm_integrations) were replaced by native Field Service, but their old
# UI records linger in installed databases and reference fields/models that no
# longer exist (e.g. fm.contract.workorder_count, model fm.workorder), which
# breaks view revalidation when fm_fsm loads. This runs early (on upgrade to the
# empty stub) and removes those doomed views/menus/actions. Idempotent.
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
)


def _delete_views(cr):
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
    remaining = {r[0] for r in cr.fetchall()}
    if not remaining:
        return
    total = len(remaining)
    while remaining:
        cr.execute(
            "SELECT id FROM ir_ui_view WHERE id IN %s "
            "AND (inherit_id IS NULL OR inherit_id NOT IN %s)",
            (tuple(remaining), tuple(remaining)),
        )
        batch = [r[0] for r in cr.fetchall()] or list(remaining)
        cr.execute("DELETE FROM ir_ui_view WHERE id IN %s", (tuple(batch),))
        remaining -= set(batch)
    _logger.info("Re-base cleanup: removed %s stale view(s)", total)


def _delete_by_module(cr, model, table):
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE model = %s AND module IN %s",
        (model, RETIRED_MODULES),
    )
    ids = [r[0] for r in cr.fetchall()]
    if ids:
        cr.execute("DELETE FROM %s WHERE id IN %%s" % table, (tuple(ids),))
        _logger.info("Re-base cleanup: removed %s %s record(s)", len(ids), model)


def migrate(cr, version):
    if not version:
        return
    # Menus first: NULL child parent_id FKs, then delete the module's menus.
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE model = 'ir.ui.menu' AND module IN %s",
        (RETIRED_MODULES,),
    )
    menu_ids = [r[0] for r in cr.fetchall()]
    if menu_ids:
        cr.execute("UPDATE ir_ui_menu SET parent_id = NULL WHERE parent_id IN %s", (tuple(menu_ids),))
        cr.execute("DELETE FROM ir_ui_menu WHERE id IN %s", (tuple(menu_ids),))
    for model, table in (
        ("ir.actions.act_window", "ir_act_window"),
        ("ir.actions.client", "ir_act_client"),
        ("ir.actions.server", "ir_act_server"),
        ("ir.actions.report", "ir_act_report_xml"),
    ):
        _delete_by_module(cr, model, table)
    _delete_views(cr)
    # Remove dangling ir_model_data anchors for any UI record now gone
    # (including ones owned by kept modules, e.g. old fm_branch WO views).
    for model, table in UI_TABLES:
        cr.execute(
            "DELETE FROM ir_model_data d WHERE d.model = %s "
            "AND NOT EXISTS (SELECT 1 FROM {t} t WHERE t.id = d.res_id)".format(t=table),
            (model,),
        )
