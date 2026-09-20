# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    """One tick on the product is what makes a sale an FM contract.

    The business writes its AMCs in Sales, from a small set of service
    products ("AMC — Pest Control", "AMC — HVAC", …). Marking those
    products once means every order that sells one is recognised as a
    facility-management contract when it is confirmed — nobody has to
    remember a checkbox on the order, and an AMC cannot be confirmed in
    Sales and then be missing from the FM app.
    """

    _inherit = "product.template"

    fm_is_contract_service = fields.Boolean(
        string="Sold as an FM Contract",
        help="Confirming a sales order that contains this product marks the "
             "order as a Facility Management contract, so it appears under "
             "FM → Contracts with its covered assets, SLA rules and "
             "visit schedule. Tick this on AMC and recurring service "
             "products; leave it off for one-off sales and materials.",
    )
