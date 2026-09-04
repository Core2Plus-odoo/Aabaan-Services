# -*- coding: utf-8 -*-
from odoo import fields, models


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
