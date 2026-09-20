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
    def test_day_based_frequency_sets_the_interval(self):
        """Weekly and fortnightly really are fixed day steps."""
        self.assertEqual(self._contract(visit_frequency="weekly")._visit_interval_days(), 7)
        self.assertEqual(
            self._contract(visit_frequency="fortnightly")._visit_interval_days(), 14)

    # ------------------------------------------------------------------
    # Recurrence dates
    #
    # The client's process document is explicit: "A job created for
    # 19-Sep-2026 on a monthly frequency must reflect on the 19th of every
    # following month." Stepping by round(365/12)=30 days put the third
    # visit on the 18th and the twelfth on the 15th.
    # ------------------------------------------------------------------
    def test_monthly_lands_on_the_same_day_of_month(self):
        order = self._contract(visit_frequency="monthly")
        dates = order._fm_visit_dates(date(2026, 9, 19), date(2027, 9, 18))
        self.assertEqual(len(dates), 12)
        self.assertEqual(
            [d.day for d in dates], [19] * 12,
            "a monthly AMC signed for the 19th must fall on the 19th every month")

    def test_month_end_start_clamps_without_walking_backwards(self):
        """31 Jan -> 28 Feb -> 31 Mar, not 28 Feb -> 28 Mar.

        Each date is anchored on the contract start, so a short month
        borrows nothing from the months after it.
        """
        order = self._contract(visit_frequency="monthly")
        dates = order._fm_visit_dates(date(2027, 1, 31), date(2027, 5, 31))
        self.assertEqual(
            [(d.month, d.day) for d in dates],
            [(1, 31), (2, 28), (3, 31), (4, 30), (5, 31)])

    def test_february_29_in_a_leap_year(self):
        order = self._contract(visit_frequency="monthly")
        dates = order._fm_visit_dates(date(2028, 1, 30), date(2028, 3, 30))
        self.assertEqual([(d.month, d.day) for d in dates],
                         [(1, 30), (2, 29), (3, 30)])

    def test_quarterly_keeps_the_date_every_three_months(self):
        order = self._contract(visit_frequency="quarterly")
        dates = order._fm_visit_dates(date(2026, 9, 19), date(2027, 9, 18))
        self.assertEqual([(d.month, d.day) for d in dates],
                         [(9, 19), (12, 19), (3, 19), (6, 19)])

    def test_weekly_keeps_the_same_weekday(self):
        """Months do not preserve weekdays, so weekly stays a day step."""
        order = self._contract(visit_frequency="weekly")
        dates = order._fm_visit_dates(date(2026, 9, 19), date(2026, 10, 24))
        self.assertEqual(len(dates), 6)
        self.assertTrue(all(d.weekday() == dates[0].weekday() for d in dates))

    def test_planned_count_matches_the_dates_actually_generated(self):
        """The number on the contract must be the number of visits."""
        order = self._contract(visit_frequency="monthly")
        start, end = order._fm_term()
        self.assertEqual(
            order._fm_planned_visit_count(),
            len(order._fm_visit_dates(start, end)) * len(order._fm_covered_assets()))

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

    # ------------------------------------------------------------------
    # Time slots
    #
    # "Every job carries exactly one time-slot tag" -- the client's process
    # document, which also publishes the three start times on its technician
    # screen: Morning 08:00, Day 13:00, Night 21:00.
    # ------------------------------------------------------------------
    def test_each_published_start_time_lands_in_its_own_slot(self):
        from odoo.addons.fm_fsm.models.fm_visit_schedule_mixin import (
            SLOT_START_HOUR, slot_for_hour,
        )
        for slot, hour in SLOT_START_HOUR.items():
            self.assertEqual(
                slot_for_hour(hour), slot,
                "%.2f is the published start of the %s slot" % (hour, slot))

    def test_slot_covers_the_whole_day(self):
        """No hour may fall outside a slot -- every job carries one tag."""
        from odoo.addons.fm_fsm.models.fm_visit_schedule_mixin import (
            TIME_SLOTS, slot_for_hour,
        )
        valid = {key for key, _label in TIME_SLOTS}
        for tenth in range(240):
            hour = tenth / 10.0
            self.assertIn(slot_for_hour(hour), valid)

    def test_choosing_a_slot_fills_in_the_start_time(self):
        order = self._contract()
        order.fm_time_slot = "night"
        order._onchange_fm_time_slot()
        self.assertEqual(order.visit_start_time, 21.0)

    def test_visit_is_tagged_from_its_planned_time(self):
        """The tag is derived, so it cannot disagree with the schedule."""
        order = self._contract(visit_frequency="monthly")
        order.fm_time_slot = "night"
        order._onchange_fm_time_slot()
        order.action_confirm()
        visits = order.fm_task_ids.filtered("planned_date_begin")
        self.assertTrue(visits, "confirming the contract should plan visits")
        for visit in visits:
            self.assertEqual(visit.fm_time_slot, "night")

    def test_rescheduling_a_visit_moves_its_tag(self):
        """Drag a job to another slot and the tag follows -- no stale tags."""
        order = self._contract(visit_frequency="monthly")
        order.action_confirm()
        visit = order.fm_task_ids.filtered("planned_date_begin")[:1]
        self.assertTrue(visit)
        visit.planned_date_begin = visit.planned_date_begin.replace(hour=21)
        self.assertEqual(visit.fm_time_slot, "night")
        visit.planned_date_begin = visit.planned_date_begin.replace(hour=8)
        self.assertEqual(visit.fm_time_slot, "morning")

    # ------------------------------------------------------------------
    # Service document gate
    #
    # "Validation must be enforced in the system logic, not optional for any
    # user role." -- the client's process document, which also shows the
    # technician's "Mark as Completed" button locked until a file is up.
    # ------------------------------------------------------------------
    def _a_visit(self):
        order = self._contract(visit_frequency="monthly")
        order.action_confirm()
        visit = order.fm_task_ids.filtered("planned_date_begin")[:1]
        self.assertTrue(visit, "confirming the contract should plan visits")
        return visit

    def _attach_report(self, visit):
        return self.env["ir.attachment"].create({
            "name": "report_%s.jpg" % visit.id,
            "res_model": "project.task",
            "res_id": visit.id,
            "datas": b"aGVsbG8=",
        })

    def test_completed_is_refused_without_a_document(self):
        visit = self._a_visit()
        completed = self.env.ref("fm_fsm.fsm_stage_completed")
        self.assertFalse(visit.fm_has_service_document)
        with self.assertRaises(UserError):
            visit.stage_id = completed

    def test_completed_is_allowed_once_a_document_is_attached(self):
        visit = self._a_visit()
        self._attach_report(visit)
        visit.invalidate_recordset(["fm_has_service_document"])
        self.assertTrue(visit.fm_has_service_document)
        visit.stage_id = self.env.ref("fm_fsm.fsm_stage_completed")
        self.assertEqual(visit.stage_id, self.env.ref("fm_fsm.fsm_stage_completed"))

    def test_signed_off_is_gated_too(self):
        """Closing a visit by skipping Completed must not dodge the gate."""
        visit = self._a_visit()
        with self.assertRaises(UserError):
            visit.stage_id = self.env.ref("fm_fsm.fsm_stage_signed_off")

    def test_pending_documents_is_always_reachable(self):
        """The stage a visit without its report belongs in is never blocked."""
        visit = self._a_visit()
        pending = self.env.ref("fm_fsm.fsm_stage_pending_docs")
        visit.stage_id = pending
        self.assertEqual(visit.stage_id, pending)

    def test_pending_documents_sorts_before_completed(self):
        pending = self.env.ref("fm_fsm.fsm_stage_pending_docs")
        completed = self.env.ref("fm_fsm.fsm_stage_completed")
        self.assertLess(
            pending.sequence, completed.sequence,
            "Pending Documents must sit before Completed on the kanban")

    def test_the_gate_is_a_stage_flag_not_a_hardcoded_id(self):
        for xmlid in ("fm_fsm.fsm_stage_completed", "fm_fsm.fsm_stage_signed_off"):
            self.assertTrue(self.env.ref(xmlid).fm_requires_document, xmlid)
        for xmlid in ("fm_fsm.fsm_stage_in_progress",
                      "fm_fsm.fsm_stage_pending_docs",
                      "fm_fsm.fsm_stage_cancelled"):
            self.assertFalse(self.env.ref(xmlid).fm_requires_document, xmlid)

    def test_awaiting_documents_filter_is_searchable(self):
        """A non-stored compute needs a search method or the filter 500s."""
        visit = self._a_visit()
        Task = self.env["project.task"]
        self.assertIn(
            visit, Task.search([("fm_has_service_document", "=", False)]))
        self._attach_report(visit)
        visit.invalidate_recordset(["fm_has_service_document"])
        self.assertIn(
            visit, Task.search([("fm_has_service_document", "=", True)]))
