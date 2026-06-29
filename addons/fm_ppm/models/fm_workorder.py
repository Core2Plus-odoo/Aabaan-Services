# -*- coding: utf-8 -*-
from odoo import fields, models


class FmWorkOrder(models.Model):
    """Link work orders back to the PPM schedule that generated them."""

    _inherit = "fm.workorder"

    parent_ppm_schedule_id = fields.Many2one("fm.ppm.schedule", string="PPM Schedule", index=True)
