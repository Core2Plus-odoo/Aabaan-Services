# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmWorkOrder(models.Model):
    _inherit = "fm.workorder"

    branch_id = fields.Many2one(
        "fm.branch", string="Branch", index=True, tracking=True,
        compute="_compute_branch_id", store=True, readonly=False,
    )

    @api.depends("contract_id")
    def _compute_branch_id(self):
        for wo in self:
            # Default from the contract's branch; stays editable afterwards.
            if wo.contract_id.branch_id and not wo.branch_id:
                wo.branch_id = wo.contract_id.branch_id
