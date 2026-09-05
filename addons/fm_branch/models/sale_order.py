# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    """Branch on the sale order itself.

    ``fm.contract`` composes with ``sale.order`` by delegation
    (``_inherits``), so holding the branch here means one field and one
    column serving both apps: a contract shows it in the FM cockpit, and
    the same value is on the quotation or order in Sales, where contracts
    are also written up.

    Keeping a separate ``branch_id`` on ``fm.contract`` would shadow this
    one and give the same contract two branches, so the field lives here
    only.
    """

    _inherit = "sale.order"

    branch_id = fields.Many2one(
        "fm.branch", string="Branch", index=True, tracking=True,
        help="The Aabaan branch delivering this contract. Groups contracts, "
             "work orders and reporting by emirate.")

    @api.onchange("branch_id")
    def _onchange_branch_id_agreement_template(self):
        """Re-suggest a wording template when the branch changes and the
        current template (if any) doesn't match this branch. Same rule as
        the legacy contract model; the lookup is shared (fm.agreement.mixin),
        only the covered-assets field name differs."""
        if not self._fm_branch_template_needs_resuggesting():
            return
        service_line = self._fm_infer_service_from_assets(self.fm_asset_ids)
        template = self._fm_branch_template_for_service(service_line)
        if template:
            self.agreement_template_id = template.id
