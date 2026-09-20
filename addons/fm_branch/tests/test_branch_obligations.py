# -*- coding: utf-8 -*-
"""What the emirate obliges us to, and what the branch contributes.

Two things are under test, and only one of them is about a warning.

The call-out allowance is a convenience: a branch's standard filled onto
a contract that has none. The test that matters there is the one
asserting it does NOT fill a contract that has one, because a term the
customer agreed to is not a default to be improved.

The visit floor is not a convenience. A Dubai food-premises contract
sold at twelve visits a year is a compliance breach that surfaces at an
inspection rather than in this system, so the constraint has to hold
through every route into the record -- which is the whole reason it is a
constraint and not a check inside the confirm button. The test for
*editing a confirmed contract down* is the one a button check would
fail.
"""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBranchObligations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Branch Obligations Customer"})
        cls.dubai = cls.env["fm.branch"].create({
            "name": "Dubai Test Branch", "emirate": "dubai",
            "licence_number": "TEST-LICENCE-1", "default_callout_allowance": 2,
        })
        cls.sharjah = cls.env["fm.branch"].create({
            "name": "Sharjah Test Branch", "emirate": "sharjah",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Pest Control Visit", "type": "service", "list_price": 300.0,
        })

    def _contract(self, **extra):
        vals = {
            "partner_id": self.partner.id,
            "is_fm_contract": True,
            "order_line": [(0, 0, {
                "product_id": self.product.id, "product_uom_qty": 1,
            })],
        }
        vals.update(extra)
        return self.env["sale.order"].create(vals)

    # ------------------------------------------------------------------
    # The licence belongs to the branch
    # ------------------------------------------------------------------
    def test_the_contract_reads_the_branch_licence(self):
        order = self._contract(branch_id=self.dubai.id)
        self.assertEqual(order.fm_licence_number, "TEST-LICENCE-1")

    def test_a_branch_with_no_licence_shows_nothing(self):
        """Blank prints nothing on the agreement, which is visibly wrong.
        A guessed number prints confidently, which is not."""
        order = self._contract(branch_id=self.sharjah.id)
        self.assertFalse(order.fm_licence_number)

    # ------------------------------------------------------------------
    # The call-out allowance
    # ------------------------------------------------------------------
    def test_confirming_fills_the_branch_allowance_when_none_is_set(self):
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="non_food",
                               visit_frequency="monthly")
        self.assertEqual(order.fm_callout_allowance, 0)
        order.action_confirm()
        self.assertEqual(order.fm_callout_allowance, 2)

    def test_confirming_says_on_the_chatter_that_it_filled_one(self):
        """A term the customer can hold us to should not appear with
        nothing on the record to say where it came from."""
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="non_food",
                               visit_frequency="monthly")
        seen = set(order.message_ids.ids)
        order.action_confirm()
        new = order.message_ids.filtered(lambda m: m.id not in seen)
        self.assertTrue(
            any("call-out allowance" in (m.body or "") for m in new),
            "confirming filled the allowance without saying so",
        )

    def test_confirming_does_not_overwrite_an_agreed_allowance(self):
        """Four was negotiated. It stays four."""
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="non_food",
                               visit_frequency="monthly", fm_callout_allowance=4)
        order.action_confirm()
        self.assertEqual(order.fm_callout_allowance, 4)

    def test_a_contract_recognised_on_confirmation_gets_the_allowance_too(self):
        """The order nobody ticked.

        fm_branch loads last, so its action_confirm runs first -- before
        fm_contract has recognised the order as a contract. Filling
        before super() would serve the contracts somebody remembered to
        tick and skip exactly the ones nobody did, which are the
        contracts least likely to carry an allowance of their own.
        """
        contract_product = self.env["product.product"].create({
            "name": "Annual Pest Control AMC",
            "type": "service",
            "list_price": 4000.0,
            "fm_is_contract_service": True,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "branch_id": self.dubai.id,
            "order_line": [(0, 0, {
                "product_id": contract_product.id, "product_uom_qty": 1,
            })],
        })
        self.assertFalse(order.is_fm_contract)
        order.action_confirm()
        self.assertTrue(order.is_fm_contract, "the order was not recognised")
        self.assertEqual(order.fm_callout_allowance, 2)

    def test_a_branch_with_no_standard_fills_nothing(self):
        order = self._contract(branch_id=self.sharjah.id, visit_frequency="monthly")
        order.action_confirm()
        self.assertEqual(order.fm_callout_allowance, 0)

    # ------------------------------------------------------------------
    # The visit floor
    # ------------------------------------------------------------------
    def test_dubai_food_premises_below_the_floor_is_refused(self):
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="food",
                               visit_frequency="monthly")  # 12 a year, floor is 24
        with self.assertRaises(ValidationError):
            order.action_confirm()
            order.flush_recordset()

    def test_dubai_food_premises_at_the_floor_confirms(self):
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="food",
                               visit_frequency="twice_monthly")  # 24 a year
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_dubai_non_food_has_the_lower_floor(self):
        """Twelve is short for a food site and exactly right for a
        non-food one. The premises type is the whole difference."""
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="non_food",
                               visit_frequency="monthly")
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_editing_a_confirmed_contract_below_the_floor_is_refused(self):
        """The hole a confirm-button check leaves. Nothing stops somebody
        confirming at twenty-four and then dropping the cadence."""
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="food",
                               visit_frequency="twice_monthly")
        order.action_confirm()
        with self.assertRaises(ValidationError):
            order.write({"visit_frequency": "monthly"})
            order.flush_recordset()

    def test_a_custom_interval_is_measured_too(self):
        """A 30-day custom interval is twelve visits a year however it is
        spelled, and must not slip past a table lookup."""
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="food",
                               visit_frequency="custom", custom_interval_days=30)
        with self.assertRaises(ValidationError):
            order.action_confirm()
            order.flush_recordset()

    # ------------------------------------------------------------------
    # Where no rule has been established, nothing is imposed
    # ------------------------------------------------------------------
    def test_sharjah_is_not_held_to_dubais_rule(self):
        """Local Order No. 11 is Dubai Municipality's. Applying it to
        Sharjah would be inventing regulation for an emirate nobody has
        checked -- and would block contracts on a rule that may not
        exist."""
        order = self._contract(branch_id=self.sharjah.id, fm_premises_type="food",
                               visit_frequency="monthly")
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_no_premises_type_means_no_floor(self):
        """Half the facts is not enough to block a contract on."""
        order = self._contract(branch_id=self.dubai.id, visit_frequency="monthly")
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_no_branch_means_no_floor(self):
        order = self._contract(fm_premises_type="food", visit_frequency="monthly")
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_a_draft_below_the_floor_still_saves(self):
        """A quotation is a negotiation. A draft that cannot be saved at
        twelve visits while somebody is still working out whether the site
        handles food would make the form unusable."""
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="food",
                               visit_frequency="monthly")
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.visit_frequency, "monthly")

    def test_an_ordinary_quotation_is_never_floored(self):
        order = self._contract(branch_id=self.dubai.id, fm_premises_type="food",
                               visit_frequency="monthly", is_fm_contract=False)
        order.action_confirm()
        self.assertEqual(order.state, "sale")
