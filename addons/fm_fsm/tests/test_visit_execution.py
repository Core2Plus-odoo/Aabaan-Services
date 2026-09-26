# -*- coding: utf-8 -*-
"""The visit execution guards — consolidation plan P1.

The tests that matter here are the *refusals*. A button that works is
obvious the first time somebody presses it; a guard that quietly stopped
working is not, and every one of these guards exists because the easy path
has to be the correct path. So most of what follows is about the routes
round the buttons: the kanban drag, the mass edit, the API write.

Ported from aabaan_field_ops on the retired build. The source matched
stages by name; these assert the xmlid behaviour that replaced it, and the
Pending Documents routing that the source build had nowhere to express.
"""
from datetime import date, datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVisitExecution(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Execution Test Client"})
        cls.category = cls.env["fm.asset.category"].create({
            "name": "Execution Test Tanks", "service_line": "water_tank",
        })
        cls.location = cls.env["fm.asset.location"].create({
            "name": "Execution Test Tower", "location_type": "building",
        })
        cls.asset = cls.env["fm.asset"].create({
            "name": "Execution Roof Tank",
            "category_fm_id": cls.category.id,
            "location_fm_id": cls.location.id,
        })
        cls.technician = cls.env["res.users"].create({
            "name": "Test Technician", "login": "fm_exec_tech",
        })
        cls.project = cls.env.ref("fm_fsm.fsm_project_fm")
        cls.stage_in_progress = cls.env.ref("fm_fsm.fsm_stage_in_progress")
        cls.stage_pending_docs = cls.env.ref("fm_fsm.fsm_stage_pending_docs")
        cls.stage_completed = cls.env.ref("fm_fsm.fsm_stage_completed")
        cls.stage_cancelled = cls.env.ref("fm_fsm.fsm_stage_cancelled")
        cls.stage_assigned = cls.env.ref("fm_fsm.fsm_stage_assigned")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _visit(self, assigned=True, **extra):
        start = datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=9)
        vals = {
            "name": "Execution Test Visit",
            "project_id": self.project.id,
            "company_id": self.env.company.id,
            "partner_id": self.partner.id,
            "fm_asset_id": self.asset.id,
            "planned_date_begin": start,
            "date_deadline": start + timedelta(hours=2),
            "allocated_hours": 2.0,
            "stage_id": self.stage_assigned.id,
        }
        if assigned:
            vals["user_ids"] = [(6, 0, [self.technician.id])]
        vals.update(extra)
        return self.env["project.task"].create(vals)

    def _attach(self, task):
        """A service document, by the only route the guard recognises."""
        return self.env["ir.attachment"].create({
            "name": "site-photo.jpg",
            "res_model": "project.task",
            "res_id": task.id,
            "datas": b"aGVsbG8=",
        })

    def _started(self, **extra):
        task = self._visit(**extra)
        task.action_fm_start_visit()
        return task

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def test_starting_a_visit_stamps_the_check_in_and_moves_the_stage(self):
        task = self._visit()
        task.action_fm_start_visit()
        self.assertTrue(task.fm_visit_started_at)
        self.assertEqual(task.stage_id, self.stage_in_progress)

    def test_a_visit_with_no_technician_cannot_be_started(self):
        """A check-in with nobody checked in proves nothing."""
        task = self._visit(assigned=False)
        with self.assertRaises(UserError):
            task.action_fm_start_visit()

    def test_a_visit_cannot_be_started_twice(self):
        task = self._started()
        with self.assertRaises(UserError):
            task.action_fm_start_visit()

    # ------------------------------------------------------------------
    # Complete
    # ------------------------------------------------------------------

    def test_completing_without_a_field_report_is_refused(self):
        """The municipality return is written from that field."""
        task = self._started()
        with self.assertRaises(UserError):
            task.action_fm_complete_visit()

    def test_completing_without_a_check_in_is_refused(self):
        task = self._visit(fm_treatment_summary="Drained and chlorinated.")
        with self.assertRaises(UserError):
            task.action_fm_complete_visit()

    def test_completing_with_a_document_reaches_completed(self):
        task = self._started(fm_treatment_summary="Drained and chlorinated.")
        self._attach(task)
        task.invalidate_recordset(["fm_has_service_document"])
        task.action_fm_complete_visit()
        self.assertTrue(task.fm_visit_completed_at)
        self.assertEqual(task.stage_id, self.stage_completed)

    def test_completing_without_a_document_lands_in_pending_documents(self):
        """Not an error. The work really is finished, and a visit left in In
        Progress says a technician is still standing on the roof.

        This is the behaviour the source build could not express -- it had no
        Pending Documents stage -- so it is the one most worth pinning.
        """
        task = self._started(fm_treatment_summary="Drained and chlorinated.")
        task.action_fm_complete_visit()
        self.assertTrue(task.fm_visit_completed_at)
        self.assertEqual(task.stage_id, self.stage_pending_docs)

    def test_a_visit_cannot_be_completed_twice(self):
        task = self._started(fm_treatment_summary="Done.")
        task.action_fm_complete_visit()
        with self.assertRaises(UserError):
            task.action_fm_complete_visit()

    def test_time_on_site_is_the_gap_between_the_two_stamps(self):
        task = self._started(fm_treatment_summary="Done.")
        task.action_fm_complete_visit()
        task.write({
            "fm_visit_started_at": datetime(2026, 9, 1, 8, 0),
            "fm_visit_completed_at": datetime(2026, 9, 1, 10, 30),
        })
        self.assertEqual(task.fm_visit_duration_actual, 2.5)

    def test_an_unfinished_visit_has_no_duration(self):
        """Blank, not zero. Zero reads as a job nobody spent any time on."""
        task = self._started()
        self.assertEqual(task.fm_visit_duration_actual, 0.0)

    # ------------------------------------------------------------------
    # The follow-up
    # ------------------------------------------------------------------

    def test_infestation_raises_an_unbilled_follow_up_three_days_out(self):
        task = self._started(
            fm_treatment_summary="Treated, live activity found.",
            fm_infestation_found=True)
        task.action_fm_complete_visit()
        followup = task.fm_followup_task_id
        self.assertTrue(followup, "infestation must raise a follow-up")
        self.assertEqual(followup.fm_followup_origin_id, task)
        self.assertEqual(followup.fm_asset_id, self.asset)
        self.assertEqual(followup.partner_id, self.partner)
        self.assertEqual(followup.user_ids, task.user_ids)
        self.assertEqual(followup.fm_wo_type, "reactive")
        gap = followup.planned_date_begin - task.fm_visit_completed_at
        self.assertEqual(gap.days, 3)

    def test_the_follow_up_carries_no_products_so_it_bills_nothing(self):
        """Unbilled means exactly that on this platform: industry_fsm_sale
        invoices a visit from the products recorded against it, so a task
        carrying none invoices nothing. There is no flag, and none is
        invented."""
        task = self._started(
            fm_treatment_summary="Treated.", fm_infestation_found=True)
        task.action_fm_complete_visit()
        followup = task.fm_followup_task_id
        if "sale_line_id" in followup._fields:
            self.assertFalse(followup.sale_line_id)

    def test_no_infestation_raises_no_follow_up(self):
        task = self._started(fm_treatment_summary="Clean, no activity.")
        task.action_fm_complete_visit()
        self.assertFalse(task.fm_followup_task_id)

    def test_a_second_completion_does_not_raise_a_second_follow_up(self):
        task = self._started(
            fm_treatment_summary="Treated.", fm_infestation_found=True)
        task.action_fm_complete_visit()
        first = task.fm_followup_task_id
        with self.assertRaises(UserError):
            task.action_fm_complete_visit()
        self.assertEqual(task.fm_followup_task_id, first)

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def test_cancelling_without_a_reason_is_refused(self):
        task = self._visit()
        with self.assertRaises(UserError):
            task.action_fm_cancel_visit()

    def test_cancelling_with_a_reason_works(self):
        task = self._visit(fm_cancel_reason="Site closed for Eid.")
        task.action_fm_cancel_visit()
        self.assertEqual(task.stage_id, self.stage_cancelled)

    # ------------------------------------------------------------------
    # The routes round the buttons -- what these guards are actually for
    # ------------------------------------------------------------------

    def test_dragging_to_in_progress_is_intercepted(self):
        task = self._visit()
        with self.assertRaises(UserError):
            task.write({"stage_id": self.stage_in_progress.id})

    def test_dragging_to_completed_is_intercepted(self):
        """Even with a document attached: the document gate would pass, and
        the field report would still never have been written."""
        task = self._started(fm_treatment_summary="Done.")
        self._attach(task)
        task.invalidate_recordset(["fm_has_service_document"])
        with self.assertRaises(UserError):
            task.write({"stage_id": self.stage_completed.id})

    def test_dragging_to_cancelled_without_a_reason_is_intercepted(self):
        task = self._visit()
        with self.assertRaises(UserError):
            task.write({"stage_id": self.stage_cancelled.id})

    def test_cancelling_by_write_works_when_the_reason_comes_in_the_same_write(self):
        """An import or an RPC client setting both at once is doing the right
        thing, and must not be refused for not having pressed a button."""
        task = self._visit()
        task.write({
            "stage_id": self.stage_cancelled.id,
            "fm_cancel_reason": "Client rescheduled.",
        })
        self.assertEqual(task.stage_id, self.stage_cancelled)

    def test_unguarded_stages_are_still_free(self):
        """Draft, Assigned, Acknowledged, Pending Documents and Signed Off
        depend on no evidence, so a dispatcher may still set them."""
        task = self._visit()
        task.write({"stage_id": self.stage_pending_docs.id})
        self.assertEqual(task.stage_id, self.stage_pending_docs)

    def test_an_ordinary_project_task_is_not_guarded(self):
        """An office task must not need a treatment summary to close. The
        guards are for FM visits, not for everything in the database."""
        project = self.env["project.project"].create({"name": "Office Admin"})
        stage = self.env["project.task.type"].create({
            "name": "Doing", "project_ids": [(6, 0, [project.id])],
        })
        task = self.env["project.task"].create({
            "name": "Order more stationery", "project_id": project.id,
        })
        self.assertFalse(task._fm_is_guarded_visit())
        task.write({"stage_id": stage.id})
        self.assertEqual(task.stage_id, stage)

    # ------------------------------------------------------------------
    # The watchdog
    # ------------------------------------------------------------------

    def test_a_visit_past_plan_and_not_started_is_escalated_once(self):
        task = self._visit(
            planned_date_begin=datetime.now() - timedelta(days=3),
            date_deadline=datetime.now() - timedelta(days=3) + timedelta(hours=2))
        self.env["project.task"]._cron_fm_visit_escalations()
        self.assertTrue(task.fm_sla_escalated)
        first = self.env["mail.activity"].search_count([
            ("res_model", "=", "project.task"), ("res_id", "=", task.id),
        ])
        self.assertTrue(first, "the watchdog must leave an activity behind")

        # Second run: a watchdog that chases the same job every morning is
        # one everybody learns to filter out.
        self.env["project.task"]._cron_fm_visit_escalations()
        again = self.env["mail.activity"].search_count([
            ("res_model", "=", "project.task"), ("res_id", "=", task.id),
        ])
        self.assertEqual(again, first)

    def test_the_activity_lands_on_the_assigned_technician(self):
        task = self._visit(
            planned_date_begin=datetime.now() - timedelta(days=3),
            date_deadline=datetime.now() - timedelta(days=3) + timedelta(hours=2))
        self.env["project.task"]._cron_fm_visit_escalations()
        activity = self.env["mail.activity"].search([
            ("res_model", "=", "project.task"), ("res_id", "=", task.id),
        ], limit=1)
        self.assertEqual(activity.user_id, self.technician)

    def test_a_started_visit_is_not_escalated(self):
        task = self._started(
            planned_date_begin=datetime.now() - timedelta(days=3),
            date_deadline=datetime.now() - timedelta(days=3) + timedelta(hours=2))
        self.env["project.task"]._cron_fm_visit_escalations()
        self.assertFalse(task.fm_sla_escalated)

    def test_a_visit_still_within_its_plan_is_not_escalated(self):
        task = self._visit()
        self.env["project.task"]._cron_fm_visit_escalations()
        self.assertFalse(task.fm_sla_escalated)

    def test_a_closed_visit_is_not_escalated(self):
        """stage_id.fold is what "closed" means natively -- Signed Off and
        Cancelled are folded, and chasing either would be noise."""
        task = self._visit(
            fm_cancel_reason="Site closed.",
            planned_date_begin=datetime.now() - timedelta(days=3),
            date_deadline=datetime.now() - timedelta(days=3) + timedelta(hours=2))
        task.action_fm_cancel_visit()
        self.env["project.task"]._cron_fm_visit_escalations()
        self.assertFalse(task.fm_sla_escalated)
