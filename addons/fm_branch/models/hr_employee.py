# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    fm_branch_id = fields.Many2one("fm.branch", string="FM Branch", index=True)
