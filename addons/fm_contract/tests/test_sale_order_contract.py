# -*- coding: utf-8 -*-
"""A contract is a sale order.

These tests hold the two design rules the layer rests on:

* an ordinary quotation must be unaffected by the FM fields, and
* confirming the order is what makes the contract live.

Both are easy to break later without noticing, because neither shows up
until someone tries to save a quotation that has nothing to do with
facility management.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleOrderContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "FM Contract Order Test"})
        cls.product = cls.env["product.product"].create({
            "name": "Quarterly Pest Control Visit",
            "type": "service",
            "list_price": 500.0,
        })

    def _order_vals(self, **extra):
        vals = {
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 500.0,
            })],
        }
        vals.update(extra)
        return vals

    # ------------------------------------------------------------------
    # An ordinary quotation is untouched
    # ------------------------------------------------------------------
    def test_a_plain_quotation_still_saves(self):
        """Nothing on this layer is required at column level, because most
        orders in this database are not contracts and never will be."""
        order = self.env["sale.order"].create(self._order_vals())
        self.assertFalse(order.is_fm_contract)
        self.assertFalse(order.fm_contract_number)
        self.assertFalse(order.fm_lifecycle)

    def test_a_plain_quotation_burns_no_contract_number(self):
        """Contract numbers are handed out when an order becomes a
        contract. A quotation that takes one leaves a gap in the customer's
        contract numbering that nothing explains."""
        order = self.env["sale.order"].create(self._order_vals())
        self.assertFalse(order.fm_contract_number)

    def test_confirming_a_plain_quotation_leaves_the_lifecycle_empty(self):
        order = self.env["sale.order"].create(self._order_vals())
        order.action_confirm()
        self.assertFalse(order.fm_lifecycle)

    # ------------------------------------------------------------------
    # A contract
    # ------------------------------------------------------------------
    def test_flagging_an_order_assigns_a_contract_number(self):
        order = self.env["sale.order"].create(self._order_vals(is_fm_contract=True))
        self.assertTrue(order.fm_contract_number)

    def test_flagging_an_existing_order_assigns_a_contract_number(self):
        """The flag can be ticked after the fact, on an order that was
        raised as an ordinary quotation and then became a contract."""
        order = self.env["sale.order"].create(self._order_vals())
        self.assertFalse(order.fm_contract_number)
        order.is_fm_contract = True
        self.assertTrue(order.fm_contract_number)

    def test_contract_numbers_are_not_reissued(self):
        """Writing the flag again must not hand out a second number."""
        order = self.env["sale.order"].create(self._order_vals(is_fm_contract=True))
        first = order.fm_contract_number
        order.write({"is_fm_contract": True})
        self.assertEqual(order.fm_contract_number, first)

    def test_confirming_the_order_activates_the_contract(self):
        """One action, one meaning: the customer agreed, so the order is
        confirmed and the contract starts. There is no window where the
        order is confirmed and the contract is not."""
        order = self.env["sale.order"].create(self._order_vals(is_fm_contract=True))
        self.assertFalse(order.fm_lifecycle)
        order.action_confirm()
        self.assertEqual(order.fm_lifecycle, "active")

    def test_confirming_does_not_reset_a_moved_contract(self):
        """A contract already moved on (terminated, in renewal) is not
        dragged back to Active by a later confirm."""
        order = self.env["sale.order"].create(self._order_vals(is_fm_contract=True))
        order.action_confirm()
        order.action_fm_terminate()
        order.action_confirm()
        self.assertEqual(order.fm_lifecycle, "terminated")

    def test_lifecycle_buttons_refuse_non_contracts(self):
        """An ordinary quotation has no contract stage to move, and saying
        so beats silently stamping one on it."""
        order = self.env["sale.order"].create(self._order_vals())
        with self.assertRaises(UserError):
            order.action_fm_terminate()

    # ------------------------------------------------------------------
    # Term and commercials
    # ------------------------------------------------------------------
    def test_tcv_follows_acv_over_the_term(self):
        order = self.env["sale.order"].create(self._order_vals(
            is_fm_contract=True,
            fm_acv=12000.0,
            fm_start_date="2026-01-01",
            fm_end_date="2027-12-31",
        ))
        # Two years, near enough: the compute divides real days by 365.
        self.assertGreater(order.fm_tcv, 23000.0)
        self.assertLess(order.fm_tcv, 25000.0)

    def test_tcv_falls_back_to_acv_without_a_term(self):
        order = self.env["sale.order"].create(self._order_vals(
            is_fm_contract=True, fm_acv=12000.0,
        ))
        self.assertEqual(order.fm_tcv, 12000.0)

    # ------------------------------------------------------------------
    # SLA rules and penalties hang off the order
    # ------------------------------------------------------------------
    def test_sla_rules_attach_to_the_order(self):
        order = self.env["sale.order"].create(self._order_vals(is_fm_contract=True))
        rule = self.env["fm.sla.rule"].create({
            "order_id": order.id,
            "name": "P1 response",
            "severity": "p1_critical",
            "response_target_minutes": 60,
            "resolution_target_minutes": 240,
        })
        self.assertIn(rule, order.fm_sla_rule_ids)
        self.assertEqual(rule.currency_id, order.currency_id)

    def test_penalty_clauses_attach_to_the_order(self):
        order = self.env["sale.order"].create(self._order_vals(is_fm_contract=True))
        penalty = self.env["fm.contract.penalty"].create({
            "order_id": order.id,
            "name": "SLA breach credit",
            "amount": 250.0,
        })
        self.assertIn(penalty, order.fm_penalty_clause_ids)
        self.assertEqual(penalty.currency_id, order.currency_id)

    # ------------------------------------------------------------------
    # Printed agreement wording
    # ------------------------------------------------------------------
    def test_a_new_contract_starts_with_editable_wording(self):
        """There is always visible, editable text in the form from the
        moment the order exists, not only after a template is picked."""
        order = self.env["sale.order"].create(self._order_vals(is_fm_contract=True))
        self.assertTrue(order.quotation_intro_text)
        self.assertTrue(order.scope_method_text)
        self.assertTrue(order.service_text)
        self.assertTrue(order.schedule_text)
        self.assertTrue(order.exclusions_text)

    def test_switching_template_never_leaves_the_previous_wording(self):
        """The rule that was once a bug: every wording field is reset to the
        new template's value or the generic default, never left holding the
        previous template's text."""
        template_a = self.env["fm.contract.agreement.template"].create({
            "name": "Template A",
            "service_line": "pest",
            "schedule_text": "Wording that belongs to template A only.",
        })
        template_b = self.env["fm.contract.agreement.template"].create({
            "name": "Template B",
            "service_line": "termite",
        })
        order = self.env["sale.order"].new(self._order_vals(is_fm_contract=True))
        order.agreement_template_id = template_a
        order._onchange_agreement_template_id()
        self.assertEqual(order.schedule_text, "Wording that belongs to template A only.")
        order.agreement_template_id = template_b
        order._onchange_agreement_template_id()
        self.assertNotIn("template A", order.schedule_text)
