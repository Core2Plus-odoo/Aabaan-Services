# -*- coding: utf-8 -*-
"""Visits follow the sale order.

The tests that matter here are the ones about *not* generating: the
generator writes into people's calendars, and the failure mode that costs
real money is a second set of visits appearing for a job already scheduled.
"""
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVisitSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Visit Schedule Test"})
        cls.category = cls.env["fm.asset.category"].create({
            "name": "Test Water Tanks",
            "service_line": "water_tank",
        })
        cls.location = cls.env["fm.asset.location"].create({
            "name": "Test Tower",
            "location_type": "building",
        })
        cls.asset = cls.env["fm.asset"].create({
            "name": "Roof Tank A",
            "category_fm_id": cls.category.id,
            "location_fm_id": cls.location.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Quarterly Tank Cleaning",
            "type": "service",
            "list_price": 500.0,
        })

    def _contract(self, **extra):
        vals = {
            "partner_id": self.partner.id,
            "is_fm_contract": True,
            "fm_start_date": date.today(),
            "fm_end_date": date.today() + timedelta(days=365),
            "fm_asset_ids": [(6, 0, [self.asset.id])],
            "visit_frequency": "monthly",
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 500.0,
            })],
        }
        vals.update(extra)
        return self.env["sale.order"].create(vals)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def test_visits_are_generated_and_linked_to_the_order(self):
        order = self._contract()
        created = order._generate_schedule()
        self.assertTrue(created)
        self.assertEqual(created.fm_contract_order_id, order)
        self.assertEqual(created.mapped("fm_asset_id"), self.asset)

    def test_generated_visits_show_on_the_order(self):
        order = self._contract()
        order._generate_schedule()
        self.assertTrue(order.fm_task_ids)
        self.assertEqual(order.fm_task_count, len(order.fm_task_ids))

    def test_generation_is_idempotent(self):
        """Running twice must not double-book an asset. This is the whole
        reason the consolidation started: two sets of visits for the same
        job, with nothing on screen to say why."""
        order = self._contract()
        first = order._generate_schedule()
        self.assertTrue(first)
        second = order._generate_schedule()
        self.assertFalse(second)

    def test_confirming_the_order_fills_the_horizon(self):
        """No separate step to forget: agreeing the order is what puts the
        visits in the calendar."""
        order = self._contract()
        self.assertFalse(order.fm_task_ids)
        order.action_confirm()
        self.assertTrue(order.fm_task_ids)

    def test_a_plain_quotation_generates_nothing_on_confirm(self):
        order = self._contract(is_fm_contract=False)
        order.action_confirm()
        self.assertFalse(order.fm_task_ids)

    def test_auto_schedule_off_generates_nothing_on_confirm(self):
        order = self._contract(auto_schedule=False)
        order.action_confirm()
        self.assertFalse(order.fm_task_ids)

    # ------------------------------------------------------------------
    # Cadence
    # ------------------------------------------------------------------
    def test_frequency_sets_the_interval(self):
        order = self._contract(visit_frequency="quarterly")
        self.assertEqual(order._visit_interval_days(), round(365 / 4))

    def test_custom_interval_is_honoured(self):
        order = self._contract(visit_frequency="custom", custom_interval_days=45)
        self.assertEqual(order._visit_interval_days(), 45)

    def test_custom_interval_falls_back_rather_than_dividing_by_zero(self):
        order = self._contract(visit_frequency="custom", custom_interval_days=0)
        self.assertEqual(order._visit_interval_days(), 30)

    def test_skip_weekends_moves_visits_to_a_working_day(self):
        order = self._contract()
        saturday = date(2026, 9, 5)
        self.assertEqual(saturday.weekday(), 5)
        self.assertEqual(order._next_working_day(saturday).weekday(), 0)

    def test_weekends_are_kept_when_the_option_is_off(self):
        order = self._contract(skip_weekends=False)
        saturday = date(2026, 9, 5)
        self.assertEqual(order._next_working_day(saturday), saturday)

    # ------------------------------------------------------------------
    # Guards on the manual button
    # ------------------------------------------------------------------
    def test_generating_without_assets_says_so(self):
        order = self._contract(fm_asset_ids=[(5, 0, 0)])
        with self.assertRaises(UserError):
            order.action_generate_visits()

    def test_generating_without_a_term_says_so(self):
        order = self._contract(fm_start_date=False, fm_end_date=False)
        with self.assertRaises(UserError):
            order.action_generate_visits()

    def test_generating_twice_says_nothing_was_left_to_do(self):
        """Silence after a button press reads as a broken button."""
        order = self._contract()
        order.action_generate_visits()
        with self.assertRaises(UserError):
            order.action_generate_visits()

    # ------------------------------------------------------------------
    # The link back
    # ------------------------------------------------------------------
    def test_a_visit_resolves_its_contract_order(self):
        order = self._contract()
        visit = order._generate_schedule()[0]
        self.assertEqual(visit._fm_contract_order(), order)

    def test_a_visit_takes_the_customer_from_the_contract(self):
        order = self._contract()
        visit = order._generate_schedule()[0]
        self.assertEqual(visit.partner_id, self.partner)
