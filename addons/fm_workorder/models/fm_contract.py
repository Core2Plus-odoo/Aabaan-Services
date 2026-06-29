# -*- coding: utf-8 -*-
from odoo import fields, models


class FmContract(models.Model):
    """Extends fm.contract with work-order back-references, resolving the
    contract↔work-order circular dependency (the One2many lives here, in the
    module that defines fm.workorder).
    """

    _inherit = "fm.contract"

    workorder_ids = fields.One2many("fm.workorder", "contract_id", string="Work Orders")
    workorder_count = fields.Integer(compute="_compute_workorder_count")

    def _compute_workorder_count(self):
        groups = self.env["fm.workorder"]._read_group(
            [("contract_id", "in", self.ids)], ["contract_id"], ["__count"]
        )
        counts = {c.id: n for c, n in groups}
        for contract in self:
            contract.workorder_count = counts.get(contract.id, 0)

    def action_view_workorders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Work Orders",
            "res_model": "fm.workorder",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id, "default_customer_id": self.partner_id.id},
        }
