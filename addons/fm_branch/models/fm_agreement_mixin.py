# -*- coding: utf-8 -*-
from odoo import models


class FmAgreementMixin(models.AbstractModel):
    """Branch-aware wording-template lookup, for everything that can be a
    contract.

    The override lives on the mixin rather than on one contract model so it
    reaches every one of them at once: a contract written in Sales gets the
    Dubai wording for the same reason a legacy ``fm.contract`` did. When the
    legacy model goes, nothing here has to move.

    ``branch_id`` is defined on ``sale.order`` (see sale_order.py) and
    reaches ``fm.contract`` through the ``_inherits`` delegation, so both
    models answer ``self.branch_id`` and this one implementation serves them.
    """

    _inherit = "fm.agreement.mixin"

    def _find_agreement_template(self, service_line):
        """Prefer a template matching both this contract's branch and the
        given service line; fall back to the base (service-line-only)
        lookup."""
        Template = self.env["fm.contract.agreement.template"]
        if self.branch_id:
            template = Template.search(
                [("service_line", "=", service_line), ("branch_id", "=", self.branch_id.id)],
                limit=1,
            )
            if template:
                return template
        return super()._find_agreement_template(service_line)

    def _fm_branch_template_for_service(self, service_line):
        """The template to suggest when the branch changes: the best match
        for this branch and service, or any template for this branch when
        the service isn't known yet."""
        if service_line:
            return self._find_agreement_template(service_line)
        return self.env["fm.contract.agreement.template"].search(
            [("branch_id", "=", self.branch_id.id)], limit=1
        )

    def _fm_branch_template_needs_resuggesting(self):
        """True when the branch is set and the current template (if any)
        does not belong to it — e.g. the user picked a branch after already
        picking a generic or other-branch template. A template that already
        matches is never overridden."""
        if not self.branch_id:
            return False
        return not (
            self.agreement_template_id
            and self.agreement_template_id.branch_id == self.branch_id
        )
