# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    """One tick decides that a product bills on a recurrence.

    Companion to ``fm_is_contract_service`` in fm_contract: that flag makes
    an order an FM contract, this one makes it bill as a subscription. Two
    flags rather than one because the two are genuinely separate decisions
    — plenty of AMCs are invoiced by hand or annually against a milestone,
    and enrolling those in recurring billing would start sending customers
    invoices nobody asked for.

    Ticking it also ticks Odoo's own ``recurring_invoice``. A subscription
    order needs at least one recurring product or Odoo refuses to confirm
    it, and the moment to settle that is here, while somebody is setting
    the product up — not in the middle of confirming a customer's order.
    """

    _inherit = "product.template"

    fm_bills_as_subscription = fields.Boolean(
        string="Bills as a Subscription",
        help="Confirming a Facility Management contract that sells this "
             "product puts the order on a subscription plan matching its "
             "billing frequency, and Odoo's own subscription engine raises "
             "the recurring invoices from then on. Leave it off for AMCs "
             "invoiced by hand, annually, or against milestones.",
    )

    def _fm_sync_recurring_invoice(self, vals):
        """Keep Odoo's recurring flag in step with ours, never the reverse.

        Only ever switched *on*: a product can be recurring for reasons
        that have nothing to do with FM, and un-ticking our flag must not
        quietly stop somebody else's subscription from billing.
        """
        if not vals.get("fm_bills_as_subscription"):
            return
        if "recurring_invoice" not in self._fields:
            return
        stragglers = self.filtered(lambda p: not p.recurring_invoice)
        if stragglers:
            stragglers.recurring_invoice = True

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        for product, vals in zip(products, vals_list):
            product._fm_sync_recurring_invoice(vals)
        return products

    def write(self, vals):
        res = super().write(vals)
        self._fm_sync_recurring_invoice(vals)
        return res
