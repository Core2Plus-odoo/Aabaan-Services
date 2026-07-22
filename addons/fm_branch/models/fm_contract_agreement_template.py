# -*- coding: utf-8 -*-
from odoo import fields, models


class FmContractAgreementTemplate(models.Model):
    """State-wise (branch/Emirate) agreement wording, alongside the
    service-wise wording fm_contract already provides — a template can be
    scoped to a branch, a service line, both, or neither (generic)."""

    _inherit = "fm.contract.agreement.template"

    branch_id = fields.Many2one(
        "fm.branch",
        string="Branch",
        index=True,
        help="Restrict this wording to one branch/Emirate, e.g. different "
        "governing-law or municipal wording per office. Leave blank for a "
        "template usable by any branch.",
    )
    emirate = fields.Selection(related="branch_id.emirate", store=True, readonly=True)
