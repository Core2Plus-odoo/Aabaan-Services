# -*- coding: utf-8 -*-
from odoo import fields, models


class FmContract(models.Model):
    _inherit = "fm.contract"

    branch_id = fields.Many2one("fm.branch", string="Branch", index=True, tracking=True)
