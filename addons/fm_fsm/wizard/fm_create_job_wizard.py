# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.fm_contract.models.sale_order import DURATION_UNITS, duration_delta

from ..models.sale_order import job_dates


class FmCreateJobWizard(models.TransientModel):
    """Create Job on a Draft contract.

    The job plan — one off or recurring, from when, for how long, and each
    service's frequency — is set here, at the moment the jobs are made,
    rather than spread over the quotation's lines and the contract tab. It
    is saved back onto the contract and its lines, and the preview shows
    the exact dates that will be created.
    """
    _name = "fm.create.job.wizard"
    _description = "Create Job"

    order_id = fields.Many2one("sale.order", required=True, readonly=True)
    partner_id = fields.Many2one(related="order_id.partner_id")
    job_type = fields.Selection(
        [("one_off", "One Off"), ("recurring", "Recurring")],
        string="Job Type", required=True, default="recurring")
    start_date = fields.Date(
        string="Start Date", required=True, default=fields.Date.context_today)
    duration = fields.Integer(string="Duration", default=1)
    duration_unit = fields.Selection(DURATION_UNITS, string="Duration Unit", default="year")
    end_date = fields.Date(string="End Date", compute="_compute_end_date")
    line_ids = fields.One2many("fm.create.job.wizard.line", "wizard_id", string="Services")
    job_count = fields.Integer(string="Jobs to create", compute="_compute_job_count")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order = self.env["sale.order"].browse(res.get("order_id") or self.env.context.get("default_order_id"))
        if order:
            res.update({
                "job_type": order.fm_job_type or "recurring",
                "start_date": order.fm_start_date or fields.Date.context_today(self),
                "duration": order.fm_duration or 1,
                "duration_unit": order.fm_duration_unit or "year",
                "line_ids": [(0, 0, {
                    "sale_line_id": line.id,
                    "create_job": line.fm_creates_job,
                    "every": line.fm_frequency_every,
                    "count": line.fm_frequency_count or 1,
                    "unit": line.fm_frequency_unit or "year",
                }) for line in order._fm_product_lines()],
            })
        return res

    @api.depends("start_date", "duration", "duration_unit")
    def _compute_end_date(self):
        for wizard in self:
            if wizard.start_date and wizard.duration > 0 and wizard.duration_unit:
                wizard.end_date = (wizard.start_date
                                   + duration_delta(wizard.duration, wizard.duration_unit)
                                   - relativedelta(days=1))
            else:
                wizard.end_date = False

    @api.depends("line_ids.job_count")
    def _compute_job_count(self):
        for wizard in self:
            wizard.job_count = sum(wizard.line_ids.mapped("job_count"))

    def action_create_jobs(self):
        self.ensure_one()
        order = self.order_id
        if not self.line_ids.filtered("create_job"):
            raise UserError(_(
                "No service is ticked Create Job. Tick at least one, or add "
                "the service lines on the contract first."))
        if not self.end_date:
            raise UserError(_("Set the Duration."))
        if self.job_type == "recurring" and any(
                l.count < 1 for l in self.line_ids.filtered("create_job")):
            raise UserError(_("Every service needs a frequency of at least 1."))
        order.write({
            "fm_job_type": self.job_type,
            "fm_start_date": self.start_date,
            "fm_duration": self.duration,
            "fm_duration_unit": self.duration_unit,
        })
        for line in self.line_ids:
            line.sale_line_id.write({
                "fm_creates_job": line.create_job,
                "fm_frequency_every": line.every,
                "fm_frequency_count": line.count,
                "fm_frequency_unit": line.unit,
            })
        return order.action_fm_create_jobs()


class FmCreateJobWizardLine(models.TransientModel):
    _name = "fm.create.job.wizard.line"
    _description = "Create Job — Service"

    wizard_id = fields.Many2one("fm.create.job.wizard", required=True, ondelete="cascade")
    sale_line_id = fields.Many2one("sale.order.line", string="Service", required=True, readonly=True)
    create_job = fields.Boolean(string="Create Job", default=True)
    product_id = fields.Many2one(related="sale_line_id.product_id")
    every = fields.Boolean(
        string="Every",
        help="Ticked: one job every N units (Every 3 Month). "
             "Unticked: N jobs per unit (4 per Year).")
    count = fields.Integer(string="Frequency", default=1)
    unit = fields.Selection(DURATION_UNITS, string="Per", default="year")
    job_count = fields.Integer(string="Jobs", compute="_compute_dates")
    dates_preview = fields.Char(string="Dates", compute="_compute_dates")

    @api.depends("create_job", "every", "count", "unit", "wizard_id.job_type",
                 "wizard_id.start_date", "wizard_id.end_date")
    def _compute_dates(self):
        for line in self:
            wizard = line.wizard_id
            order = wizard.order_id
            dates = [order._next_working_day(d) for d in job_dates(
                wizard.job_type, line.count, line.unit, line.every,
                wizard.start_date, wizard.end_date)] if order and line.create_job else []
            line.job_count = len(dates)
            shown = ", ".join(d.strftime("%d %b %Y") for d in dates[:6])
            line.dates_preview = shown + (" … +%s more" % (len(dates) - 6) if len(dates) > 6 else "")
