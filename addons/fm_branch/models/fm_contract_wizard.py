# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmContractWizard(models.TransientModel):
    """Branch (state/Emirate) on the guided contract wizard — drives the
    state-wise template match and lands on the created contract."""

    _inherit = "fm.contract.wizard"

    branch_id = fields.Many2one(
        "fm.branch", string="Branch / Emirate",
        help="Which Aabaan office serves this contract — also selects "
        "state-specific agreement wording where one exists (e.g. Dubai "
        "Pest Control).",
    )

    @api.onchange("branch_id")
    def _onchange_branch_id_template(self):
        if self.service_line:
            self.template_id = self._find_wizard_template()

    def _find_wizard_template(self):
        Template = self.env["fm.contract.agreement.template"]
        if self.branch_id and self.service_line:
            template = Template.search(
                [("service_line", "=", self.service_line), ("branch_id", "=", self.branch_id.id)],
                limit=1,
            )
            if template:
                return template
        return super()._find_wizard_template()

    def _prepare_contract_vals(self):
        vals = super()._prepare_contract_vals()
        if self.branch_id:
            vals["branch_id"] = self.branch_id.id
        return vals
