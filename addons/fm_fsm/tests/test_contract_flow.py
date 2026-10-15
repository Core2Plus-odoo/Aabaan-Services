# -*- coding: utf-8 -*-
"""Quotation -> Approve -> Draft contract -> Create Job -> Approved.

What has to hold: approving makes no job of any kind (the native
one-task-per-service-line included), and Create Job is the only thing that
puts a contract's visits on the calendar — with or without covered assets.
"""
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestContractFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Contract Flow Test"})
        # A service that makes a task on confirm, like the client's products:
        # the case where approving must not create a job.
        cls.project = cls.env["project.project"].create({"name": "Flow Test Project"})
        cls.product = cls.env["product.product"].create({
            "name": "Flow Test Service",
            "type": "service",
            "list_price": 500.0,
            "invoice_policy": "order",
            "service_tracking": "task_global_project",
            "project_id": cls.project.id,
        })

    def _quotation(self, **extra):
        vals = {
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})],
        }
        vals.update(extra)
        return self.env["sale.order"].create(vals)

    def _jobs(self, order):
        return self.env["project.task"].search([
            "|", ("sale_order_id", "=", order.id), ("fm_contract_order_id", "=", order.id)])

    def test_approve_makes_a_draft_contract_and_no_job(self):
        order = self._quotation()
        self.assertEqual(order.fm_quote_status, "draft")
        order.action_fm_approve()
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.fm_quote_status, "approved")
        self.assertTrue(order.is_fm_contract)
        self.assertEqual(order.fm_lifecycle, "draft")
        self.assertTrue(order.fm_contract_number)
        self.assertFalse(self._jobs(order))
        self.assertEqual(order.invoice_status, "to invoice")

    def test_only_an_open_quotation_can_be_approved(self):
        order = self._quotation()
        order.action_fm_approve()
        with self.assertRaises(UserError):
            order.action_fm_approve()

    def _approved_dates(self, job_type="recurring", duration=1, unit="year", **line):
        order = self._quotation()
        order.order_line.write(line)
        order.action_fm_approve()
        order.write({
            "fm_job_type": job_type,
            "fm_start_date": date(2026, 10, 14),
            "fm_duration": duration,
            "fm_duration_unit": unit,
            "skip_weekends": False,
        })
        order.action_fm_create_jobs()
        return order, [t.planned_date_begin.date() for t in order.fm_task_ids.sorted("planned_date_begin")]

    def test_duration_sets_the_end_a_day_short(self):
        order, _dates = self._approved_dates(job_type="one_off")
        self.assertEqual(order.fm_end_date, date(2027, 10, 13))

    def test_one_off_is_one_job_on_the_start_date(self):
        order, dates = self._approved_dates(job_type="one_off")
        self.assertEqual(dates, [date(2026, 10, 14)])
        self.assertEqual(order.fm_lifecycle, "active")
        self.assertFalse(order.fm_task_ids.fm_asset_id)
        self.assertEqual(order.fm_task_ids.sale_line_id, order.order_line)

    def test_four_a_year_is_every_three_months(self):
        _order, dates = self._approved_dates(fm_frequency_count=4, fm_frequency_unit="year")
        self.assertEqual(dates, [date(2026, 10, 14), date(2027, 1, 14),
                                 date(2027, 4, 14), date(2027, 7, 14)])

    def test_twice_a_month_over_a_month_is_today_and_15_days_on(self):
        _order, dates = self._approved_dates(
            duration=1, unit="month", fm_frequency_count=2, fm_frequency_unit="month")
        self.assertEqual(dates, [date(2026, 10, 14), date(2026, 10, 29)])

    def test_every_three_months(self):
        _order, dates = self._approved_dates(
            fm_frequency_count=3, fm_frequency_unit="month", fm_frequency_every=True)
        self.assertEqual(len(dates), 4)
        self.assertEqual(dates[1], date(2027, 1, 14))

    def test_create_job_runs_once(self):
        order, _dates = self._approved_dates(job_type="one_off")
        with self.assertRaises(UserError):
            order.action_fm_create_jobs()

    def test_the_wizard_sets_the_plan_and_creates_the_jobs(self):
        order = self._quotation()
        order.action_fm_approve()
        action = order.action_fm_open_create_job()
        wizard = self.env[action["res_model"]].with_context(**action["context"]).create({})
        self.assertEqual(wizard.line_ids.sale_line_id, order.order_line)
        wizard.write({"start_date": date(2026, 10, 14), "duration": 1, "duration_unit": "year"})
        wizard.line_ids.write({"count": 4, "unit": "year"})
        order.skip_weekends = False
        self.assertEqual(wizard.job_count, 4)
        wizard.action_create_jobs()
        self.assertEqual(order.fm_lifecycle, "active")
        self.assertEqual(order.fm_start_date, date(2026, 10, 14))
        self.assertEqual(order.fm_end_date, date(2027, 10, 13))
        self.assertEqual(order.order_line.fm_frequency_count, 4)
        self.assertEqual(len(order.fm_task_ids), 4)
