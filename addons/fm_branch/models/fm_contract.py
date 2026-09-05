# -*- coding: utf-8 -*-
from odoo import api, models


class FmContract(models.Model):
    """Branch-aware contract behaviour (legacy contract model).

    ``branch_id`` itself is defined on ``sale.order`` (see sale_order.py)
    and reaches this model through the ``_inherits`` delegation, so the
    same value shows on the contract in FM and on the order in Sales.
    Defining it here as well would shadow that one and split the contract
    across two branches.

    The template lookup itself is in fm_agreement_mixin.py, shared with
    contracts written in Sales; only the onchange wiring is here, because
    the field it reads (``asset_ids``) is this model's own name for it.
    """

    _inherit = "fm.contract"

    @api.onchange("branch_id")
    def _onchange_branch_id_agreement_template(self):
        """Re-suggest a wording template when the branch changes and the
        current template (if any) doesn't match this branch."""
        if not self._fm_branch_template_needs_resuggesting():
            return
        service_line = self._fm_infer_service_from_assets(self.asset_ids)
        template = self._fm_branch_template_for_service(service_line)
        if template:
            self.agreement_template_id = template.id
