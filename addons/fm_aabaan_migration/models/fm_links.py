# -*- coding: utf-8 -*-
from odoo import fields, models


class FmContract(models.Model):
    """Origin link so migration is idempotent."""

    _inherit = "fm.contract"

    aabaan_contract_id = fields.Many2one(
        "aabaan.service.contract", string="Migrated From", readonly=True, copy=False, index=True
    )


class FmWorkOrder(models.Model):
    _inherit = "fm.workorder"

    aabaan_visit_id = fields.Many2one(
        "aabaan.service.visit", string="Migrated From Visit", readonly=True, copy=False, index=True
    )
