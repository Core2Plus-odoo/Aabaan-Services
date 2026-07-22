# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmContractWizard(models.TransientModel):
    """Branch (state/Emirate) on the guided contract wizard — drives the
    state-wise template match and lands on every created contract."""

    _inherit = "fm.contract.wizard"

    branch_id = fields.Many2one(
        "fm.branch", string="Branch / Emirate",
        help="Which Aabaan office serves this contract — also selects "
        "state-specific agreement wording where one exists (e.g. Dubai "
        "Pest Control).",
    )

    @api.depends("branch_id")
    def _compute_template_preview(self):
        # Extend the compute's dependencies so changing the branch refreshes
        # the matched-agreements preview (the branch decides which template
        # _find_wizard_template returns).
        super()._compute_template_preview()

    def _find_wizard_template(self, service_line):
        Template = self.env["fm.contract.agreement.template"]
        if self.branch_id and service_line:
            template = Template.search(
                [("service_line", "=", service_line), ("branch_id", "=", self.branch_id.id)],
                limit=1,
            )
            if template:
                return template
        return super()._find_wizard_template(service_line)

    def _prepare_contract_vals(self, category, template):
        vals = super()._prepare_contract_vals(category, template)
        if self.branch_id:
            vals["branch_id"] = self.branch_id.id
        return vals
