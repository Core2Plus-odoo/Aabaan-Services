# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectTask(models.Model):
    """Branch dimension on native Field Service tasks."""

    _inherit = "project.task"

    branch_id = fields.Many2one(
        "fm.branch", string="Branch", index=True, tracking=True,
        compute="_compute_branch_id", store=True, readonly=False,
    )

    @api.depends("fm_contract_id")
    def _compute_branch_id(self):
        for task in self:
            # Default from the contract's branch; stays editable afterwards.
            if task.fm_contract_id.branch_id and not task.branch_id:
                task.branch_id = task.fm_contract_id.branch_id
