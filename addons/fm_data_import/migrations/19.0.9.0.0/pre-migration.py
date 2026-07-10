# -*- coding: utf-8 -*-
"""Retire fm_data_import: purge its residual DB records FK-safe on the production upgrade.

This module carried only wizard/config models (no business data), so the purge
is: menus -> actions -> views (transitive-closure children, leaves first) ->
model metadata (access, fields, model) -> table(s) -> dangling ir_model_data.
Idempotent; safe to run repeatedly. See CLAUDE.md section 5.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = "fm_data_import"
DEFUNCT_MODELS = ("odoo.master.data.config", "odoo.master.data.import.wizard",)
# Postgres tables to drop outright (self-owned data, incl. any stored secrets).
DROP_TABLES = ("odoo_master_data_config",)


def _res_ids(cr, imd_model):
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE module = %s AND model = %s",
        (MODULE, imd_model),
    )
    return [r[0] for r in cr.fetchall()]


def _delete_menus(cr):
    ids = _res_ids(cr, "ir.ui.menu")
    if ids:
        cr.execute("UPDATE ir_ui_menu SET parent_id = NULL WHERE id IN %s", (tuple(ids),))
        cr.execute("DELETE FROM ir_ui_menu WHERE id IN %s", (tuple(ids),))


def _delete_actions(cr):
    mapping = {
        "ir.actions.act_window": "ir_act_window",
        "ir.actions.client": "ir_act_client",
        "ir.actions.report": "ir_act_report_xml",
        "ir.actions.server": "ir_act_server",
    }
    for model, tbl in mapping.items():
        ids = _res_ids(cr, model)
        if ids:
            cr.execute("DELETE FROM %s WHERE id IN %%s" % tbl, (tuple(ids),))
            cr.execute("DELETE FROM ir_actions WHERE id IN %s", (tuple(ids),))


def _delete_views(cr):
    ids = set(_res_ids(cr, "ir.ui.view"))
    if not ids:
        return
    # Expand to the transitive closure of inheriting children.
    frontier = set(ids)
    while frontier:
        cr.execute("SELECT id FROM ir_ui_view WHERE inherit_id IN %s", (tuple(frontier),))
        children = {r[0] for r in cr.fetchall()} - ids
        ids |= children
        frontier = children
    # Delete leaves first (views with no surviving child in the doomed set).
    remaining = set(ids)
    while remaining:
        cr.execute(
            "SELECT id FROM ir_ui_view WHERE id IN %s "
            "AND (inherit_id IS NULL OR inherit_id NOT IN %s)",
            (tuple(remaining), tuple(remaining)),
        )
        leaves = {r[0] for r in cr.fetchall()} or remaining
        cr.execute("DELETE FROM ir_ui_view WHERE id IN %s", (tuple(leaves),))
        remaining -= leaves


def _delete_model_meta(cr):
    for model in DEFUNCT_MODELS:
        cr.execute("SELECT id FROM ir_model WHERE model = %s", (model,))
        row = cr.fetchone()
        if not row:
            continue
        mid = row[0]
        cr.execute("DELETE FROM ir_model_access WHERE model_id = %s", (mid,))
        cr.execute("DELETE FROM ir_model_constraint WHERE model = %s", (mid,))
        cr.execute("DELETE FROM ir_model_fields WHERE model_id = %s", (mid,))
        cr.execute("DELETE FROM ir_model WHERE id = %s", (mid,))


def _drop_tables(cr):
    for tbl in DROP_TABLES:
        cr.execute("DROP TABLE IF EXISTS %s CASCADE" % tbl)


def migrate(cr, version):
    _delete_menus(cr)
    _delete_actions(cr)
    _delete_views(cr)
    _delete_model_meta(cr)
    _drop_tables(cr)
    cr.execute("DELETE FROM ir_model_data WHERE module = %s", (MODULE,))
    _logger.info("Retired %s: residual records purged.", MODULE)
