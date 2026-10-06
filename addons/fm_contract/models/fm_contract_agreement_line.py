# -*- coding: utf-8 -*-
from odoo import fields, models

from .fm_contract_agreement_template import LINE_KINDS


class FmContractAgreementLine(models.Model):
    """One custom article on a contract's printed agreement — the contract's
    own editable copy of a template line (see
    SaleOrder._onchange_agreement_template_id); freely addable/editable
    without touching the shared template.

    Lived in fm_contract.py alongside the legacy ``fm.contract`` model until
    that model was dropped. Nothing about this one was legacy: it is the
    order's list of extra articles and the Service Agreement PDF prints it.
    """

    _name = "fm.contract.agreement.line"
    _description = "FM Contract Agreement — Additional Term"
    _order = "sequence, id"

    order_id = fields.Many2one(
        "sale.order", string="Contract", ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    kind = fields.Selection(LINE_KINDS, default="article", required=True)
    name = fields.Char(string="Heading", required=True)
    body = fields.Text(string="Body", required=True)
    body_html = fields.Html(string="Body (formatted)")
