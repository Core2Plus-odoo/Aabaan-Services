# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

UNIT_DELTA = {
    "day": "days",
    "week": "weeks",
    "month": "months",
    "quarter": "months",  # ×3
    "year": "years",
}


class FmPpmSchedule(models.Model):
    """Preventive maintenance schedule (brief §5.4). A daily cron generates
    PPM work orders ``wo_lead_days`` ahead of ``next_due``.
    """

    _name = "fm.ppm.schedule"
    _description = "FM PPM Schedule"
    _order = "next_due"

    name = fields.Char(required=True)
    asset_id = fields.Many2one("fm.asset", required=True, index=True)
    company_id = fields.Many2one(related="asset_id.company_id", store=True)
    checklist_template_id = fields.Many2one("fm.checklist.template", required=True)
    trigger_type = fields.Selection(
        [
            ("time", "Time-based"),
            ("meter", "Meter-based"),
            ("mixed", "Time or Meter — whichever first"),
        ],
        required=True,
        default="time",
    )
    frequency_value = fields.Integer(default=1)
    frequency_unit = fields.Selection(
        [
            ("day", "Days"),
            ("week", "Weeks"),
            ("month", "Months"),
            ("quarter", "Quarters"),
            ("year", "Years"),
        ],
        default="month",
    )
    meter_threshold = fields.Float()
    last_completed = fields.Datetime(readonly=True)
    next_due = fields.Datetime(compute="_compute_next_due", store=True)
    auto_generate_wo = fields.Boolean(default=True)
    wo_lead_days = fields.Integer(string="Generate WO N days before due", default=7)
    active = fields.Boolean(default=True)
    generated_wo_ids = fields.One2many("fm.workorder", "parent_ppm_schedule_id")
    generated_wo_count = fields.Integer(compute="_compute_generated_wo_count")

    @api.depends("last_completed", "frequency_value", "frequency_unit", "create_date")
    def _compute_next_due(self):
        for sched in self:
            anchor = sched.last_completed or sched.create_date or fields.Datetime.now()
            value = sched.frequency_value or 1
            if sched.frequency_unit == "quarter":
                delta = relativedelta(months=value * 3)
            else:
                delta = relativedelta(**{UNIT_DELTA.get(sched.frequency_unit, "months"): value})
            sched.next_due = anchor + delta

    def _compute_generated_wo_count(self):
        for sched in self:
            sched.generated_wo_count = len(sched.generated_wo_ids)

    def _create_ppm_workorder(self):
        self.ensure_one()
        wo = self.env["fm.workorder"].create(
            {
                "wo_type": "ppm",
                "severity": "p3_medium",
                "asset_id": self.asset_id.id,
                # Customer defaults to the company partner until the asset→
                # contract→customer link exists (fm_contract adds asset.contract_id).
                "customer_id": self.asset_id.company_id.partner_id.id,
                "company_id": self.asset_id.company_id.id,
                "problem_description": "Planned preventive maintenance: %s" % self.name,
                "checklist_template_id": self.checklist_template_id.id,
                "schedule_date_start": self.next_due,
                "parent_ppm_schedule_id": self.id,
            }
        )
        return wo

    @api.model
    def _cron_generate_ppm_workorders(self):
        today = fields.Date.context_today(self)
        schedules = self.search([("active", "=", True), ("auto_generate_wo", "=", True)])
        for sched in schedules:
            if not sched.next_due:
                continue
            trigger_on = fields.Datetime.to_datetime(sched.next_due) - relativedelta(days=sched.wo_lead_days)
            if trigger_on.date() > today:
                continue
            # Skip if an open PPM WO already exists for this cycle
            open_wo = sched.generated_wo_ids.filtered(
                lambda w: w.stage not in ("signed_off", "cancelled")
            )
            if open_wo:
                continue
            sched._create_ppm_workorder()
