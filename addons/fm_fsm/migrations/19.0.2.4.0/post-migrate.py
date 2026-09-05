# -*- coding: utf-8 -*-
"""Re-point the auto-schedule cron from fm.contract to sale.order.

``data/cron.xml`` is ``noupdate="1"``, so editing the source leaves the
installed record exactly as it was. Without this the cron would still name
``fm.contract`` and call ``_cron_auto_schedule()`` on it: a method that no
longer exists there, on a model being retired. The cron is inactive, so
nothing fails today; it would fail the first time anyone switched it on, or
the day the model goes.

Deliberately does NOT change ``active``. Whether an unattended generator
writes into people's calendars is a decision for a person, and a migration
quietly flipping it on would be exactly the silent scheduling this
consolidation exists to stop.

Uses the ORM rather than raw SQL because ``ir.cron`` reaches ``model_id``
through its ``ir.actions.server`` delegation, and ``model_name`` is a stored
related field on that record; writing the column directly would leave it
holding the old model's name.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

CRON_XMLID = "fm_fsm.cron_fm_fsm_auto_schedule"
CRON_NAME = "FM: Auto-schedule Field Service visits (off by default)"


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref(CRON_XMLID, raise_if_not_found=False)
    if not cron:
        _logger.info("FM auto-schedule cron not present; nothing to re-point.")
        return

    if cron.model_id.model == "sale.order":
        _logger.info("FM auto-schedule cron already reads sale.order.")
        return

    target = env["ir.model"]._get("sale.order")
    if not target:
        _logger.warning(
            "sale.order not in ir_model; leaving the FM auto-schedule cron on %s.",
            cron.model_id.model or "an unknown model",
        )
        return

    was = cron.model_id.model or "an unknown model"
    cron.write({"model_id": target.id, "name": CRON_NAME})
    _logger.info(
        "FM auto-schedule cron re-pointed from %s to sale.order (left %s).",
        was,
        "active" if cron.active else "inactive",
    )
