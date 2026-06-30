# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

# Contract billing frequency -> subscription plan recurrence (value, unit).
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


class FmContract(models.Model):
    """Bill the contract as a recurring subscription via sale_subscription.
    The contract delegates to sale.order, so the order lines (products &
    services) are the recurring lines and the plan sets the recurrence.
    """

    _inherit = "fm.contract"

    subscription_plan_id = fields.Many2one(
        "sale.subscription.plan", related="sale_order_id.plan_id", readonly=False, string="Subscription Plan"
    )
    is_subscription = fields.Boolean(related="sale_order_id.is_subscription", string="Is Subscription")
    subscription_state = fields.Selection(related="sale_order_id.subscription_state", string="Subscription Status")

    def _get_or_create_plan(self):
        """Find (or create) a subscription plan matching the contract's
        billing frequency."""
        self.ensure_one()
        value, unit = FREQUENCY_TO_PERIOD.get(self.billing_frequency, (1, "month"))
        Plan = self.env["sale.subscription.plan"]
        plan = Plan.search(
            [("billing_period_value", "=", value), ("billing_period_unit", "=", unit)], limit=1
        )
        if not plan:
            plan = Plan.create({
                "name": "FM %s" % PERIOD_LABEL.get(self.billing_frequency, "Recurring"),
                "billing_period_value": value,
                "billing_period_unit": unit,
            })
        return plan

    def action_start_subscription(self):
        """Set the recurrence plan from the billing frequency and confirm the
        order so the standard subscription engine takes over recurring
        invoicing of the product/service lines."""
        self.ensure_one()
        order = self.sale_order_id
        if not order.order_line:
            raise UserError(_("Add at least one product/service line to the contract before starting the subscription."))
        if not order.plan_id:
            order.plan_id = self._get_or_create_plan().id
        if order.state in ("draft", "sent"):
            order.action_confirm()
        self.message_post(body=_("Subscription started on plan %s.") % order.plan_id.display_name)
        return True

    def action_open_subscription(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Subscription"),
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
        }
