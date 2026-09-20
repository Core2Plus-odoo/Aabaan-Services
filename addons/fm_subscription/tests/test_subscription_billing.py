# -*- coding: utf-8 -*-
"""Recurring billing starts when the contract is confirmed.

Before this, the only way to start a subscription was a button on
fm.contract -- a frozen model nothing creates any more, reached through an
admin-only "Contracts (legacy)" menu. Every AMC written as a sale order had
no way to bill recurrently at all, and nothing said so.

These tests hold the two halves of the fix: the plan is set for a contract
that opted in, and it is not set for one that did not.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSubscriptionBilling(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "FM Subscription Test"})

    def _product(self, name, **extra):
        vals = {"name": name, "type": "service"}
        vals.update(extra)
        return self.env["product.product"].create(vals)

    def _order(self, product, **extra):
        vals = {
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1})],
        }
        vals.update(extra)
        return self.env["sale.order"].create(vals)

    # ------------------------------------------------------------------
    # The product flag
    # ------------------------------------------------------------------
    def test_the_flag_also_marks_the_product_recurring(self):
        """A subscription order needs a recurring product or Odoo refuses to
        confirm it. Settling that while somebody sets the product up beats
        discovering it halfway through confirming a customer's order."""
        product = self._product("AMC — Monthly Cleaning", fm_bills_as_subscription=True)
        if "recurring_invoice" not in product._fields:
            self.skipTest("recurring_invoice is not on product in this build")
        self.assertTrue(product.recurring_invoice)

    def test_unticking_does_not_stop_someone_elses_subscription(self):
        """Our flag only ever switches Odoo's on. A product can be recurring
        for reasons that have nothing to do with facility management."""
        product = self._product("AMC — HVAC", fm_bills_as_subscription=True)
        if "recurring_invoice" not in product._fields:
            self.skipTest("recurring_invoice is not on product in this build")
        product.fm_bills_as_subscription = False
        self.assertTrue(product.recurring_invoice)

    # ------------------------------------------------------------------
    # Confirmation
    # ------------------------------------------------------------------
    def test_confirming_puts_an_opted_in_contract_on_a_plan(self):
        product = self._product("AMC — Pest Control", fm_bills_as_subscription=True)
        order = self._order(product, is_fm_contract=True, fm_billing_frequency="quarterly")
        self.assertFalse(order.plan_id)
        order.action_confirm()
        self.assertTrue(order.plan_id)
        self.assertEqual(order.plan_id.billing_period_value, 3)
        self.assertEqual(order.plan_id.billing_period_unit, "month")

    def test_a_contract_that_did_not_opt_in_bills_nothing_recurrently(self):
        """Plenty of AMCs are invoiced by hand or against milestones.
        Enrolling those would send customers invoices nobody asked for."""
        product = self._product("AMC — Annual Inspection")
        order = self._order(product, is_fm_contract=True)
        order.action_confirm()
        self.assertFalse(order.plan_id)

    def test_an_existing_plan_is_left_alone(self):
        """An order somebody already put on a plan keeps it: the frequency
        is a default, not an override of a decision already taken."""
        product = self._product("AMC — Water Tank", fm_bills_as_subscription=True)
        order = self._order(product, is_fm_contract=True, fm_billing_frequency="monthly")
        chosen = order._fm_get_or_create_plan()
        order.plan_id = chosen.id
        order.action_confirm()
        self.assertEqual(order.plan_id, chosen)

    def test_the_same_cadence_does_not_grow_a_second_plan(self):
        """Two plans called Monthly in the list is how a recurrence gets
        picked wrong."""
        product = self._product("AMC — Facade", fm_bills_as_subscription=True)
        first = self._order(product, is_fm_contract=True, fm_billing_frequency="monthly")
        first.action_confirm()
        second = self._order(product, is_fm_contract=True, fm_billing_frequency="monthly")
        second.action_confirm()
        self.assertEqual(first.plan_id, second.plan_id)
