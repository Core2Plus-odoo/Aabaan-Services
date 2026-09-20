# -*- coding: utf-8 -*-
"""A quotation template carries the whole contract profile.

Written against fm_fsm because that is the module that can see both
halves: fm_contract puts the commercial profile on the template and
fm_fsm adds the cadence, so only here can a test assert that one
dropdown fills all of it.

The test that matters is the one about *editing*: a profile that cannot
be overridden is not a shortcut, it is a straitjacket, and the thing
that makes it overridable is a single `readonly=False` on eight computed
fields -- easy to drop, and nothing else would notice.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestContractProfile(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Profile Test Customer"})
        cls.manager = cls.env["res.users"].create({
            "name": "Account Manager", "login": "fm_profile_am_test",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Quarterly Pest Control", "type": "service", "list_price": 900.0,
        })
        cls.profile = cls.env["sale.order.template"].create({
            "name": "Pest Control AMC — Standard",
            "fm_is_contract_profile": True,
            "fm_service_line": "pest",
            "fm_contract_type": "amc_comprehensive",
            "fm_term_months": 24,
            "fm_billing_frequency": "quarterly",
            "fm_account_manager_id": cls.manager.id,
            "fm_visit_frequency": "twice_monthly",
            "fm_visit_day_1": 5,
            "fm_visit_day_2": 20,
            "fm_time_slot": "day",
            "fm_visit_duration_hours": 3.0,
            "fm_skip_weekends": False,
            "sale_order_template_line_ids": [(0, 0, {
                "product_id": cls.product.id, "product_uom_qty": 4,
            })],
        })
        cls.plain = cls.env["sale.order.template"].create({
            "name": "Ordinary Consultancy Package",
        })

    def _order(self, template):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        order.sale_order_template_id = template.id
        return order

    def test_a_profile_fills_the_contract(self):
        order = self._order(self.profile)
        self.assertTrue(order.is_fm_contract)
        self.assertEqual(order.fm_service_line, "pest")
        self.assertEqual(order.fm_contract_type, "amc_comprehensive")
        self.assertEqual(order.fm_billing_frequency, "quarterly")
        self.assertEqual(order.fm_account_manager_id, self.manager)

    def test_a_profile_fills_the_visit_cadence(self):
        order = self._order(self.profile)
        self.assertEqual(order.visit_frequency, "twice_monthly")
        self.assertEqual(order.visit_day_1, 5)
        self.assertEqual(order.visit_day_2, 20)
        self.assertEqual(order.fm_time_slot, "day")
        self.assertEqual(order.visit_duration_hours, 3.0)
        self.assertFalse(order.skip_weekends)

    def test_the_slot_sets_the_start_time(self):
        """The time is the single source of truth and the slot its label,
        so a profile must fill the time too -- the form's onchange does not
        run for an order built without anybody opening it."""
        order = self._order(self.profile)
        self.assertEqual(order.visit_start_time, 13.0, "Day slot starts at 13:00")

    def test_the_term_becomes_the_end_date(self):
        order = self._order(self.profile)
        self.assertTrue(order.fm_start_date, "a contract starts today by default")
        self.assertEqual(
            order.fm_end_date,
            order.fm_start_date + relativedelta(months=24),
            "24 months on from the start",
        )

    def test_a_hand_set_start_date_still_drives_the_term(self):
        order = self._order(self.profile)
        order.fm_start_date = date(2027, 3, 1)
        self.assertEqual(order.fm_end_date, date(2029, 3, 1))

    def test_every_filled_field_stays_editable(self):
        """The readonly=False on the computes. Without it a profile is a
        straitjacket, and the contract that differs slightly goes back to
        being written from a blank order."""
        order = self._order(self.profile)
        order.write({
            "fm_contract_type": "break_fix",
            "fm_billing_frequency": "annual",
            "visit_frequency": "monthly",
            "visit_duration_hours": 1.5,
            "fm_end_date": date(2030, 1, 1),
        })
        self.assertEqual(order.fm_contract_type, "break_fix")
        self.assertEqual(order.fm_billing_frequency, "annual")
        self.assertEqual(order.visit_frequency, "monthly")
        self.assertEqual(order.visit_duration_hours, 1.5)
        self.assertEqual(order.fm_end_date, date(2030, 1, 1))

    def test_a_start_date_already_typed_is_not_overwritten(self):
        """The profile fills the start date only when there isn't one.

        Regression: the compute originally read `order.fm_start_date` to
        decide. A compute's own fields are protected while it runs, and a
        protected read on an unsaved record returns False -- so it always
        looked empty and always overwrote. Silently, and it moves the end
        date, the visit schedule and the billing with it.
        """
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "fm_start_date": date(2027, 6, 1),
        })
        order.sale_order_template_id = self.profile.id
        self.assertEqual(order.fm_start_date, date(2027, 6, 1))
        self.assertEqual(order.fm_end_date, date(2029, 6, 1))

    def test_a_non_profile_template_keeps_a_hand_ticked_contract(self):
        """Same defect, other direction: picking an ordinary template must
        not silently untick a contract somebody marked by hand."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_fm_contract": True,
            "fm_service_line": "water_tank",
        })
        order.sale_order_template_id = self.plain.id
        self.assertTrue(order.is_fm_contract)
        self.assertEqual(order.fm_service_line, "water_tank")

    def test_skip_weekends_defaults_to_on_without_a_template(self):
        """Making a field computed must not change its default.

        skip_weekends is default=True on the mixin. The no-profile branch
        reads _origin, which is empty on a new record -- so reading it
        blindly turned the default into False and let visits land on
        Fri/Sat.
        """
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertTrue(order.skip_weekends)

    def test_a_profile_can_turn_weekend_skipping_off(self):
        order = self._order(self.profile)
        self.assertFalse(order.skip_weekends, "the profile sets it False")

    def test_an_ordinary_template_makes_an_ordinary_quotation(self):
        """A quotation template that is not a contract profile must not
        drag an unrelated sale into the FM app."""
        order = self._order(self.plain)
        self.assertFalse(order.is_fm_contract)
        self.assertFalse(order.fm_service_line)

    def test_an_order_with_no_template_is_untouched(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertFalse(order.is_fm_contract)
        self.assertEqual(order.visit_frequency, "monthly", "the field default stands")

    def test_a_contract_written_by_hand_still_works(self):
        """Ticking the box on a blank order is still a contract. The
        computes must not clear what a user set without a template."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_fm_contract": True,
            "fm_service_line": "water_tank",
            "fm_start_date": date(2027, 1, 1),
            "fm_end_date": date(2027, 12, 31),
        })
        self.assertTrue(order.is_fm_contract)
        self.assertEqual(order.fm_service_line, "water_tank")
        self.assertEqual(order.fm_end_date, date(2027, 12, 31))
