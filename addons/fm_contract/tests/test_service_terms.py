# -*- coding: utf-8 -*-
"""The contracted service terms: what an AMC promises beyond its price.

These fields came off a Studio layer built on the database, where they
had real consequences -- a call-out is refused once the allowance is
spent -- and no tests. The consequences are ported in later steps; this
is the part that has to be right first, because a promise stored wrongly
is worse than one not stored at all.

Two rules are worth holding down:

* a term the customer agreed to is not rewritten by a template, and
* "same day" means a fixed number of hours, not a vague intention.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestContractServiceTerms(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Service Terms Customer"})
        cls.profile = cls.env["sale.order.template"].create({
            "name": "Food Premises Pest AMC",
            "fm_is_contract_profile": True,
            "fm_premises_type": "food",
            "fm_complaint_sla": "same_day",
            "fm_callout_allowance": 2,
            "fm_followup_days": 3,
            "fm_warranty_years": 1,
        })

    def _order(self, template=None):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        if template:
            order.sale_order_template_id = template.id
        return order

    # ------------------------------------------------------------------
    # The response promise is a number
    # ------------------------------------------------------------------
    def test_same_day_is_eight_hours(self):
        """The client's own call-out logger reads same-day as eight hours.
        If this ever becomes twenty-four, every same-day contract silently
        gets three times longer to respond."""
        order = self._order()
        order.fm_complaint_sla = "same_day"
        self.assertEqual(order.fm_complaint_sla_hours, 8)

    def test_each_response_band_has_its_hours(self):
        order = self._order()
        for band, hours in (("same_day", 8), ("24h", 24), ("48h", 48)):
            order.fm_complaint_sla = band
            self.assertEqual(order.fm_complaint_sla_hours, hours, band)

    def test_no_response_promise_is_zero_hours_not_a_default(self):
        """A contract that promises nothing must not read as promising
        something. Zero is 'unstated', and the caller decides what to do
        with that -- inventing a fallback here would put a promise on a
        contract nobody signed."""
        order = self._order()
        self.assertFalse(order.fm_complaint_sla)
        self.assertEqual(order.fm_complaint_sla_hours, 0)

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    def test_a_bare_order_promises_nothing(self):
        """No term has a standing value on the contract itself. Call-outs
        depend on the emirate, warranty on the service, and the follow-up
        window on the kind of agreement -- none of which a blank order
        knows. A default here would print a promise on the agreement of
        every contract already in the database, including the ones signed
        before anybody wrote the promise down."""
        order = self._order()
        self.assertEqual(order.fm_callout_allowance, 0)
        self.assertEqual(order.fm_warranty_years, 0)
        self.assertEqual(order.fm_followup_days, 0)
        self.assertFalse(order.fm_premises_type)

    def test_the_standing_follow_up_figure_lives_on_the_profile(self):
        """Three days is the client's standing rule, so it is the
        template's default and reaches the contract through it."""
        bare = self.env["sale.order.template"].create({
            "name": "Any Contract Profile", "fm_is_contract_profile": True,
        })
        self.assertEqual(bare.fm_followup_days, 3)
        self.assertEqual(self._order(bare).fm_followup_days, 3)

    # ------------------------------------------------------------------
    # The profile fills them in
    # ------------------------------------------------------------------
    def test_a_profile_fills_the_service_terms(self):
        order = self._order(self.profile)
        self.assertEqual(order.fm_premises_type, "food")
        self.assertEqual(order.fm_complaint_sla, "same_day")
        self.assertEqual(order.fm_complaint_sla_hours, 8)
        self.assertEqual(order.fm_callout_allowance, 2)
        self.assertEqual(order.fm_followup_days, 3)
        self.assertEqual(order.fm_warranty_years, 1)

    def test_the_terms_stay_editable_after_the_profile_fills_them(self):
        """A profile is a starting point. A customer who negotiated four
        free call-outs has four, and the next save does not take two of
        them back."""
        order = self._order(self.profile)
        order.fm_callout_allowance = 4
        order.fm_warranty_years = 10
        order.flush_recordset()
        order.invalidate_recordset()
        self.assertEqual(order.fm_callout_allowance, 4)
        self.assertEqual(order.fm_warranty_years, 10)

    def test_a_plain_template_does_not_wipe_agreed_terms(self):
        """Switching an order onto a template that is not a contract
        profile leaves the contract's own terms alone. The compute still
        has to assign every field -- a field it skips comes back unset,
        not unchanged -- so this is asserting the assignment, not the
        absence of one."""
        order = self._order()
        order.write({
            "fm_premises_type": "non_food",
            "fm_complaint_sla": "48h",
            "fm_callout_allowance": 5,
            "fm_followup_days": 7,
            "fm_warranty_years": 2,
        })
        plain = self.env["sale.order.template"].create({"name": "Ordinary Package"})
        order.sale_order_template_id = plain.id
        self.assertEqual(order.fm_premises_type, "non_food")
        self.assertEqual(order.fm_complaint_sla, "48h")
        self.assertEqual(order.fm_callout_allowance, 5)
        self.assertEqual(order.fm_followup_days, 7)
        self.assertEqual(order.fm_warranty_years, 2)

    def test_a_blank_on_the_profile_does_not_erase_the_contract(self):
        """A profile that says nothing about warranty is not a profile
        that says 'no warranty'. The distinction matters because zero is
        a legitimate stored value here."""
        sparse = self.env["sale.order.template"].create({
            "name": "Bare Contract Profile",
            "fm_is_contract_profile": True,
        })
        order = self._order()
        order.write({"fm_warranty_years": 10, "fm_callout_allowance": 3})
        order.sale_order_template_id = sparse.id
        self.assertEqual(order.fm_warranty_years, 10)
        self.assertEqual(order.fm_callout_allowance, 3)

    # ------------------------------------------------------------------
    # And an ordinary quotation is still untouched
    # ------------------------------------------------------------------
    def test_a_plain_quotation_saves_with_none_of_this_set(self):
        order = self._order()
        self.assertFalse(order.is_fm_contract)
        self.assertFalse(order.fm_premises_type)
