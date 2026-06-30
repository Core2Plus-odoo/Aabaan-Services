# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# How many work orders per asset per year for each cadence.
FREQUENCY_PER_YEAR = {
    "weekly": 52,
    "fortnightly": 26,
    "monthly": 12,
    "bi_monthly": 6,
    "quarterly": 4,
    "semi_annual": 2,
    "annual": 1,
}

# Rolling window the cron keeps populated ahead of today.
ROLLING_HORIZON_DAYS = 120


class FmContract(models.Model):
    """Extends fm.contract with work-order back-references and auto-scheduling:
    given a visit frequency and criteria, planned work orders are generated for
    every covered asset across the contract term — on activation and kept
    rolling by a daily cron.
    """

    _inherit = "fm.contract"

    workorder_ids = fields.One2many("fm.workorder", "contract_id", string="Work Orders")
    workorder_count = fields.Integer(compute="_compute_workorder_count")

    # Scheduling criteria
    auto_schedule = fields.Boolean(
        string="Auto-schedule Visits",
        default=True,
        help="Automatically generate planned work orders for covered assets on activation and keep a rolling horizon populated.",
    )
    visit_frequency = fields.Selection(
        [
            ("weekly", "Weekly"),
            ("fortnightly", "Every 2 Weeks"),
            ("monthly", "Monthly"),
            ("bi_monthly", "Every 2 Months"),
            ("quarterly", "Quarterly"),
            ("semi_annual", "Semi-Annual"),
            ("annual", "Annual"),
        ],
        string="Visit Frequency",
        default="monthly",
    )
    visit_hour = fields.Integer(string="Visit Start Hour", default=9, help="Hour of day (0-23) visits are scheduled to start.")
    skip_weekends = fields.Boolean(string="Skip Weekends", default=True, help="Push visits that fall on Sat/Sun to the next working day.")
    preferred_technician_id = fields.Many2one("hr.employee", string="Preferred Technician")
    planned_wo_count = fields.Integer(compute="_compute_planned_wo_count")

    def _compute_workorder_count(self):
        groups = self.env["fm.workorder"]._read_group(
            [("contract_id", "in", self.ids)], ["contract_id"], ["__count"]
        )
        counts = {c.id: n for c, n in groups}
        for contract in self:
            contract.workorder_count = counts.get(contract.id, 0)

    @api.depends("visit_frequency", "asset_ids", "start_date", "end_date")
    def _compute_planned_wo_count(self):
        for contract in self:
            per_year = FREQUENCY_PER_YEAR.get(contract.visit_frequency, 12)
            years = 1.0
            if contract.start_date and contract.end_date and contract.end_date > contract.start_date:
                years = (contract.end_date - contract.start_date).days / 365.0
            contract.planned_wo_count = max(1, round(per_year * years)) * len(contract.asset_ids)

    def action_view_workorders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Work Orders"),
            "res_model": "fm.workorder",
            "view_mode": "calendar,list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id, "default_customer_id": self.partner_id.id},
        }

    # ------------------------------------------------------------------
    # Auto-scheduling
    # ------------------------------------------------------------------
    def _next_working_day(self, day):
        self.ensure_one()
        if self.skip_weekends:
            while day.weekday() >= 5:  # 5=Sat, 6=Sun
                day += timedelta(days=1)
        return day

    def _generate_schedule(self, horizon_end=None):
        """Create planned (PPM) work orders for every covered asset at the
        contract's frequency, from the contract start up to ``horizon_end``
        (default: the contract end). Idempotent — never double-books an
        asset on a day that already has a scheduled visit.
        """
        Wo = self.env["fm.workorder"]
        created = Wo
        for c in self:
            if not (c.asset_ids and c.visit_frequency and c.start_date and c.end_date):
                continue
            per_year = FREQUENCY_PER_YEAR.get(c.visit_frequency, 12)
            interval = max(1, round(365 / per_year))
            end = min(c.end_date, horizon_end or c.end_date)
            company = c.sale_order_id.company_id or self.env.company
            tech = c.preferred_technician_id
            hour = max(0, min(23, c.visit_hour or 9))

            # Existing scheduled dates per asset, to stay idempotent.
            existing = {}
            for wo in c.workorder_ids.filtered("schedule_date_start"):
                existing.setdefault(wo.asset_id.id, set()).add(wo.schedule_date_start.date())

            vals_list = []
            for asset in c.asset_ids:
                day = c.start_date
                while day <= end:
                    sched_day = c._next_working_day(day)
                    if sched_day not in existing.setdefault(asset.id, set()):
                        start_dt = datetime.combine(sched_day, time(hour, 0))
                        vals_list.append({
                            "wo_type": "ppm",
                            "severity": "p3_medium",
                            "asset_id": asset.id,
                            "customer_id": c.partner_id.id,
                            "contract_id": c.id,
                            "company_id": company.id,
                            "technician_id": tech.id if tech else False,
                            "stage": "assigned" if tech else "draft",
                            "problem_description": _("Planned visit for %(asset)s under contract %(ref)s")
                            % {"asset": asset.display_name, "ref": c.contract_number},
                            "schedule_date_start": start_dt,
                            "schedule_date_end": start_dt + timedelta(hours=1),
                        })
                        existing[asset.id].add(sched_day)
                    day += timedelta(days=interval)
            if vals_list:
                created += Wo.create(vals_list)
        return created

    def action_generate_workorders(self):
        """Manual trigger: schedule the full remaining term now."""
        self.ensure_one()
        if not self.asset_ids:
            raise UserError(_("Add at least one covered asset before generating work orders."))
        if not self.start_date or not self.end_date or self.end_date <= self.start_date:
            raise UserError(_("Set a valid start and end date on the contract first."))
        created = self._generate_schedule()
        self.message_post(body=_("%s planned work order(s) generated.") % len(created))
        return {
            "type": "ir.actions.act_window",
            "name": _("Scheduled Work Orders"),
            "res_model": "fm.workorder",
            "view_mode": "calendar,list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id},
        }

    def action_activate(self):
        res = super().action_activate()
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=ROLLING_HORIZON_DAYS)
        for c in self:
            if c.auto_schedule:
                c._generate_schedule(horizon_end=horizon)
        return res

    @api.model
    def _cron_auto_schedule(self):
        """Keep a rolling horizon of planned visits populated for active,
        auto-scheduled contracts."""
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=ROLLING_HORIZON_DAYS)
        contracts = self.search([("state", "=", "active"), ("auto_schedule", "=", True)])
        contracts._generate_schedule(horizon_end=horizon)
