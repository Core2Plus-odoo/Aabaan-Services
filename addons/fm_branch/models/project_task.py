# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectTask(models.Model):
    """Branch dimension on native Field Service tasks."""

    _inherit = "project.task"

    branch_id = fields.Many2one(
        "fm.branch", string="Branch", index=True, tracking=True,
        compute="_compute_branch_id", store=True, readonly=False,
    )

    @api.depends("fm_contract_order_id", "fm_contract_id")
    def _compute_branch_id(self):
        for task in self:
            # Default from the contract's branch; stays editable afterwards.
            # Reads whichever contract link the visit has (see
            # project.task._fm_contract_order): a visit generated from a
            # contract written in Sales carries fm_contract_order_id, and
            # branch_id lives on the order either way.
            branch = task._fm_contract_order().branch_id
            if branch and not task.branch_id:
                task.branch_id = branch
