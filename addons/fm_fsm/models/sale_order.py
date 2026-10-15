# -*- coding: utf-8 -*-
import math
import re
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.fm_contract.models.sale_order import duration_delta

from .fm_visit_schedule_mixin import (
    FREQUENCY_PER_YEAR,
    ROLLING_HORIZON_DAYS,
    SLOT_START_HOUR,
)


def job_dates(job_type, count, unit, every, start, end):
    """The dates of one line's jobs, ``start`` to ``end`` inclusive.

    One Off: the start date only. Recurring, "N per unit" (4 per Year): N
    jobs per unit, evenly spaced — whole months when the unit divides
    (every 3 months), days otherwise (2 per Month: today and 15 days on) —
    as many as the duration holds (4 per Year over 1 Year is 4). Recurring,
    "Every N unit" (Every 3 Month): one job each N units. Months are stepped
    from the start, so the 31st stays the 31st.

    Shared by Create Job and its wizard's preview, so what the wizard shows
    is exactly what gets created.
    """
    if not start or not end or end < start:
        return []
    if job_type == "one_off":
        return [start]
    count = max(count or 1, 1)
    unit = unit or "year"
    dates = []
    if every:
        step = 0
        while step <= 5000:
            day = start + duration_delta(count * step, unit)
            if day > end:
                break
            dates.append(day)
            step += 1
        return dates
    unit_months = {"year": 12, "month": 1}.get(unit)
    unit_days = ((start + duration_delta(1, unit)) - start).days
    span_days = (end - start).days + 1
    # As many as the duration holds, a part-period counting as one: 1 per
    # Week over 14 Oct - 13 Nov is 5 (14, 21, 28 Oct, 4, 11 Nov).
    total = max(1, math.ceil(count * span_days / unit_days - 1e-9))
    for step in range(min(total, 5000)):
        if unit_months and unit_months % count == 0:
            day = start + relativedelta(months=step * unit_months // count)
        else:
            day = start + timedelta(days=int(step * unit_days / count))
        if day > end:
            break
        dates.append(day)
    return dates


class SaleOrder(models.Model):
    """Visits follow the sale order.

    A contract is a sale order, so the visit schedule hangs off the order
    too: the thing the customer agreed to is the thing that says when
    someone turns up. Confirming the order both activates the contract and
    fills its calendar, which is why there is no separate "generate the
    schedule" step to forget.

    The scheduling itself is in fm.visit.schedule.mixin — one generator for
    the whole platform, which is the point of this consolidation.
    """

    _inherit = ["sale.order", "fm.visit.schedule.mixin"]
    _name = "sale.order"

    # fm_-prefixed, like everything else this platform adds to sale.order:
    # sale_project already puts task fields on the order, and quietly
    # shadowing one of them would break native behaviour with no error.
    fm_task_ids = fields.One2many(
        "project.task", "fm_contract_order_id", string="Visits / Work Orders"
    )

    # ------------------------------------------------------------------
    # The cadence half of a contract profile
    # ------------------------------------------------------------------
    # These mirror fm.visit.schedule.mixin's fields, redefined here so the
    # quotation template can fill them -- a compute may only assign the
    # fields it declares. Each stays readonly=False, so a contract that
    # needs a different cadence than its profile is one edit away.
    visit_frequency = fields.Selection(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    custom_interval_days = fields.Integer(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    fm_visit_weekday = fields.Selection(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    visit_day_1 = fields.Integer(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    visit_day_2 = fields.Integer(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    fm_time_slot = fields.Selection(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    visit_start_time = fields.Float(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    visit_duration_hours = fields.Float(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    skip_weekends = fields.Boolean(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )

    @api.depends("sale_order_template_id")
    def _compute_fm_schedule_from_template(self):
        """Fill the visit cadence from the order's contract profile.

        Same shape as fm_contract's _compute_fm_from_template, and the same
        reason: Odoo applies a quotation template through stored editable
        computes, so this reaches orders created by import or RPC too.

        The slot sets the start time here exactly as the form's onchange
        does -- the time is the single source of truth and the slot is its
        label -- because an onchange does not run for an order built by a
        profile without anybody opening it.
        """
        for order in self:
            profile = order.sale_order_template_id
            # _origin, not the field itself: a compute's own fields are
            # protected while it runs, and a protected read on an unsaved
            # record returns False rather than the stored value. See the
            # same note in fm_contract's _compute_fm_from_template.
            saved = order._origin
            if not profile or not profile.fm_is_contract_profile:
                # A compute must assign on every record, or a new order
                # comes back with these unset rather than defaulted.
                order.visit_frequency = saved.visit_frequency or "monthly"
                order.fm_visit_weekday = saved.fm_visit_weekday
                order.custom_interval_days = saved.custom_interval_days
                order.visit_day_1 = saved.visit_day_1 or 1
                order.visit_day_2 = saved.visit_day_2 or 15
                order.fm_time_slot = saved.fm_time_slot or "morning"
                order.visit_start_time = saved.visit_start_time or 8.0
                order.visit_duration_hours = saved.visit_duration_hours or 2.0
                # `or` cannot express a boolean whose default is True, and a
                # brand-new record has no _origin to read -- so fall back to
                # the field's own default rather than to False, which is
                # what making this field computed silently did.
                order.skip_weekends = saved.skip_weekends if saved else True
                continue
            order.visit_frequency = profile.fm_visit_frequency or "monthly"
            order.fm_visit_weekday = profile.fm_visit_weekday
            order.custom_interval_days = profile.fm_custom_interval_days
            order.visit_day_1 = profile.fm_visit_day_1 or 1
            order.visit_day_2 = profile.fm_visit_day_2 or 15
            order.fm_time_slot = profile.fm_time_slot or "morning"
            order.visit_start_time = SLOT_START_HOUR.get(order.fm_time_slot, 8.0)
            order.visit_duration_hours = profile.fm_visit_duration_hours or 2.0
            order.skip_weekends = profile.fm_skip_weekends
    fm_task_count = fields.Integer(compute="_compute_fm_task_count")
    planned_visit_count = fields.Integer(compute="_compute_planned_visit_count")

    def _compute_fm_task_count(self):
        groups = self.env["project.task"]._read_group(
            [("fm_contract_order_id", "in", self.ids)], ["fm_contract_order_id"], ["__count"]
        )
        counts = {order.id: count for order, count in groups}
        for order in self:
            order.fm_task_count = counts.get(order.id, 0)

    @api.depends(
        "visit_frequency", "custom_interval_days",
        "fm_asset_ids", "fm_start_date", "fm_end_date",
    )
    def _compute_planned_visit_count(self):
        for order in self:
            order.planned_visit_count = order._fm_planned_visit_count()

    # ------------------------------------------------------------------
    # What the shared generator asks of us
    # ------------------------------------------------------------------
    def _fm_covered_assets(self):
        return self.fm_asset_ids

    def _fm_term(self):
        return self.fm_start_date, self.fm_end_date

    def _fm_contract_ref(self):
        return self.fm_contract_number or self.name

    def _fm_visit_link_vals(self):
        return {"fm_contract_order_id": self.id}

    def _fm_company(self):
        return self.company_id or self.env.company

    def _fm_agreement_placeholder_values(self):
        """{{VISITS}} -- how many visits a year this cadence delivers.

        A plain override on sale.order rather than an extension of
        fm.agreement.mixin: extending an AbstractModel only reaches the
        concrete models built before the extension is registered, and
        sale.order was composed back in fm_contract. The mixin version
        would never run, and nothing would say so.
        """
        values = super()._fm_agreement_placeholder_values()
        per_year = FREQUENCY_PER_YEAR.get(self.visit_frequency)
        if not per_year and self.visit_frequency == "custom" and self.custom_interval_days > 0:
            per_year = round(365 / self.custom_interval_days)
        values["VISITS"] = per_year or ""
        return values

    # ------------------------------------------------------------------
    # Confirming the order fills the calendar
    # ------------------------------------------------------------------
    def action_confirm(self):
        res = super().action_confirm()
        if self.env.context.get("fm_skip_auto_schedule"):
            # Approve: the contract's jobs wait for "Create Job".
            return res
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=ROLLING_HORIZON_DAYS)
        for order in self:
            if order.is_fm_contract and order.auto_schedule:
                order._generate_schedule(horizon_end=horizon)
        return res

    # ------------------------------------------------------------------
    # Create Job: the contract's jobs, from each service line's frequency
    # ------------------------------------------------------------------
    def _fm_product_lines(self):
        """The service lines: what the Create Job wizard lists. Goods are
        never jobs."""
        return self.order_line.filtered(
            lambda l: not l.display_type and not l.is_downpayment
            and l.product_id.type == "service")

    def _fm_job_lines(self):
        """The lines that become jobs: product lines ticked Create Job."""
        return self._fm_product_lines().filtered("fm_creates_job")

    def _fm_line_job_dates(self, line, start, end):
        """The dates of one line's jobs, from its own frequency."""
        return job_dates(self.fm_job_type, line.fm_frequency_count,
                         line.fm_frequency_unit, line.fm_frequency_every, start, end)

    def _fm_create_line_jobs(self):
        """Create the jobs of every job line. Idempotent: a line never gets
        a second job on a day it already has one."""
        self.ensure_one()
        Task = self.env["project.task"]
        project = self._fsm_project()
        start, end = self.fm_start_date, self.fm_end_date
        stage_draft = self.env.ref("fm_fsm.fsm_stage_draft", raise_if_not_found=False)
        stage_assigned = self.env.ref("fm_fsm.fsm_stage_assigned", raise_if_not_found=False)
        stage = stage_draft if self.auto_schedule_state == "draft" and stage_draft else stage_assigned
        tech = self.preferred_technician_id
        tech_user = tech.user_id if tech and tech.user_id else False
        duration = self.visit_duration_hours or 2.0
        vals_list, ends = [], []
        for line in self._fm_job_lines():
            dates = [self._next_working_day(d) for d in self._fm_line_job_dates(line, start, end)]
            done = {t.date_deadline.date() for t in self.fm_task_ids
                    if t.sale_line_id == line and t.date_deadline}
            title = re.sub(r"^\[[^\]]*\]\s*", "", line.product_id.display_name or line.name or "")
            for number, day in enumerate(dates, 1):
                if day in done:
                    continue
                begin = datetime.combine(day, datetime.min.time()) + timedelta(
                    hours=self.visit_start_time or 9.0)
                name = "%s — %s" % (self.partner_id.display_name, title)
                if len(dates) > 1:
                    name += " (%s/%s)" % (number, len(dates))
                vals = {
                    "name": name,
                    "project_id": project.id,
                    "company_id": self._fm_company().id,
                    "partner_id": self.partner_id.id,
                    "fm_contract_order_id": self.id,
                    "sale_line_id": line.id,
                    "fm_wo_type": "ppm",
                    "fm_severity": "p3_medium",
                    "planned_date_begin": begin,
                    "date_deadline": begin + timedelta(hours=duration),
                    "allocated_hours": duration,
                    "description": _("Job %(n)s of %(total)s for %(line)s under contract %(ref)s") % {
                        "n": number, "total": len(dates), "line": title,
                        "ref": self._fm_contract_ref()},
                }
                if stage:
                    vals["stage_id"] = stage.id
                if tech_user:
                    vals["user_ids"] = [(6, 0, [tech_user.id])]
                vals_list.append(vals)
                ends.append(vals["date_deadline"])
        created = Task.create(vals_list) if vals_list else Task
        # date_end is dropped by create() on this build; write it after.
        for task, task_end in zip(created, ends):
            task.date_end = task_end
        return created

    def action_fm_open_create_job(self):
        """Create Job: the wizard where the job plan is set."""
        self.ensure_one()
        if not self.is_fm_contract or self.fm_lifecycle != "draft":
            raise UserError(_("Create Job is for a Draft contract."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Job"),
            "res_model": "fm.create.job.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }

    def action_fm_create_jobs(self):
        """Put the Draft contract's jobs on the calendar and approve it.

        One Off: one job per service line, on the start date. Recurring:
        each service line's jobs at its own frequency, over the duration.
        """
        self.ensure_one()
        if not self.is_fm_contract or self.fm_lifecycle != "draft":
            raise UserError(_("Create Job is for a Draft contract."))
        if not self.fm_start_date:
            # The client's screen asks for the date and offers today.
            self.fm_start_date = fields.Date.context_today(self)
        if not self.fm_end_date:
            raise UserError(_("Set the Duration (or the Contract End) first."))
        if self.fm_end_date < self.fm_start_date:
            raise UserError(_("Contract End must not be before Contract Start."))
        if not self._fm_job_lines():
            raise UserError(_(
                "Add the service lines first — each one becomes the job(s) "
                "for that service."))
        created = self._fm_create_line_jobs()
        if not created and not self.fm_task_ids:
            raise UserError(_("No job date falls inside the contract duration."))
        self.fm_lifecycle = "active"
        self.message_post(body=_(
            "%s job(s) created on the calendar. The contract is now Approved.",
            len(created)))
        return {
            "type": "ir.actions.act_window",
            "name": _("%s Job(s) Created") % len(created),
            "res_model": "project.task",
            "view_mode": "list,calendar,kanban,form",
            "domain": [("id", "in", (created or self.fm_task_ids).ids)],
            "context": self._fm_visit_context(),
        }

    @api.model
    def _cron_auto_schedule(self):
        """Keep a rolling horizon of planned visits populated for active,
        auto-scheduled contracts.

        Shipped switched off. Turning it on is a deliberate decision: it
        writes visits into people's calendars unattended, and a schedule
        that appears with nothing on screen to say what made it is worse
        than one somebody pressed a button for.
        """
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=ROLLING_HORIZON_DAYS)
        contracts = self.search([
            ("is_fm_contract", "=", True),
            ("fm_lifecycle", "=", "active"),
            ("auto_schedule", "=", True),
        ])
        contracts._generate_schedule(horizon_end=horizon)
