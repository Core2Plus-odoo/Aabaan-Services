# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmContract(models.Model):
    _inherit = "fm.contract"

    branch_id = fields.Many2one("fm.branch", string="Branch", index=True, tracking=True)

    @api.onchange("branch_id")
    def _onchange_branch_id_agreement_template(self):
        """Re-suggest a wording template when the branch changes and the
        current template (if any) doesn't match this branch — e.g. the user
        picked a branch after already picking a generic/other-branch
        template. Never overrides a template that already matches."""
        if not self.branch_id:
            return
        if self.agreement_template_id and self.agreement_template_id.branch_id == self.branch_id:
            return
        lines = [l for l in self.asset_ids.mapped("service_line") if l]
        service_line = lines[0] if len(set(lines)) == 1 else False
        template = self._find_agreement_template(service_line) if service_line else (
            self.env["fm.contract.agreement.template"].search(
                [("branch_id", "=", self.branch_id.id)], limit=1
            )
        )
        if template:
            self.agreement_template_id = template.id

    def _find_agreement_template(self, service_line):
        """Prefer a template matching both this contract's branch and the
        given service line; fall back to service-line-only, then to the
        base (service-line-only) lookup."""
        Template = self.env["fm.contract.agreement.template"]
        if self.branch_id:
            template = Template.search(
                [("service_line", "=", service_line), ("branch_id", "=", self.branch_id.id)],
                limit=1,
            )
            if template:
                return template
        return super()._find_agreement_template(service_line)
