# -*- coding: utf-8 -*-
from odoo import _, models

# Contract billing frequency -> subscription plan recurrence (value, unit).
# Lived in fm_contract.py until the legacy fm.contract layer was removed;
# it is the order's billing frequency that is mapped now.
FREQUENCY_TO_PERIOD = {
    "monthly": (1, "month"),
    "quarterly": (3, "month"),
    "semi_annual": (6, "month"),
    "annual": (1, "year"),
}

PERIOD_LABEL = {
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "semi_annual": "Semi-Annual",
    "annual": "Annual",
}


class SaleOrder(models.Model):
    """Confirming an AMC is what starts its recurring billing.

    The contract is a sale order, so the subscription hangs off the order
    too. The plan is set *before* ``super().action_confirm()`` reaches
    Odoo's own ``_action_confirm``, because that is where the native
    subscription engine picks the recurrence up — set it afterwards and
    the order is confirmed as an ordinary sale that happens to name a
    plan, which bills nobody.

    This module extends sale.order from the outermost layer of the chain
    (fm_subscription loads after fm_contract and fm_fsm), so "before
    super()" here is genuinely before everything else that hangs off
    confirmation.

    Nothing is enrolled by accident: only an order selling a product
    ticked "Bills as a Subscription" is touched, and an order that
    already names a plan is left exactly as it is.
    """

    _inherit = "sale.order"

    def _fm_subscription_products(self):
        self.ensure_one()
        return self.order_line.product_id.filtered("fm_bills_as_subscription")

    def _fm_get_or_create_plan(self):
        """The subscription plan matching this contract's billing frequency.

        Reuses whatever plan already exists for that cadence rather than
        creating a second one — two "Monthly" plans in the list is how a
        recurrence gets picked wrong.
        """
        self.ensure_one()
        frequency = self.fm_billing_frequency
        value, unit = FREQUENCY_TO_PERIOD.get(frequency, (1, "month"))
        Plan = self.env["sale.subscription.plan"]
        plan = Plan.search([
            ("billing_period_value", "=", value),
            ("billing_period_unit", "=", unit),
        ], limit=1)
        if not plan:
            plan = Plan.create({
                "name": "FM %s" % PERIOD_LABEL.get(frequency, "Recurring"),
                "billing_period_value": value,
                "billing_period_unit": unit,
            })
        return plan

    def _fm_set_subscription_plans(self):
        """Put every order selling a subscription product on its plan."""
        for order in self:
            if order.plan_id or order.state not in ("draft", "sent"):
                continue
            products = order._fm_subscription_products()
            if not products:
                continue
            plan = order._fm_get_or_create_plan()
            order.plan_id = plan.id
            order.message_post(body=_(
                "Recurring billing starts on confirmation: %(products)s "
                "bill as a subscription, so this contract was put on the "
                "%(plan)s plan, matching its %(frequency)s billing "
                "frequency.",
                products=", ".join(products.mapped("display_name")),
                plan=plan.display_name,
                frequency=PERIOD_LABEL.get(order.fm_billing_frequency, "recurring").lower(),
            ))

    def action_confirm(self):
        self._fm_set_subscription_plans()
        return super().action_confirm()
