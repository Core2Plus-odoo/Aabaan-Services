# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# How many visits per asset per year for each cadence.
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
    """Contract-driven auto-scheduling on native Field Service.

    Standard-first re-base of the old fm_workorder/fm_ppm engine: given a visit
    frequency and criteria, planned **FSM tasks** (``project.task`` in the FM
    Field Service project) are generated for every covered asset across the
    term — on activation and kept rolling by a daily cron. No bespoke work-order
    model; the visits are native FSM tasks that inherit planning, mobile
    worksheets, timesheets and billing.
    """

    _inherit = "fm.contract"

    task_ids = fields.One2many("project.task", "fm_contract_id", string="Visits / Work Orders")
    task_count = fields.Integer(compute="_compute_task_count")

    auto_schedule = fields.Boolean(
        string="Auto-schedule Visits",
        default=True,
        help="Automatically generate planned Field Service visits for covered "
        "assets on activation and keep a rolling horizon populated.",
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
    skip_weekends = fields.Boolean(
        string="Skip Weekends",
        default=True,
        help="Push visits that fall on Sat/Sun to the next working day.",
    )
    preferred_technician_id = fields.Many2one("hr.employee", string="Preferred Technician")
    planned_visit_count = fields.Integer(compute="_compute_planned_visit_count")

    def _compute_task_count(self):
        groups = self.env["project.task"]._read_group(
            [("fm_contract_id", "in", self.ids)], ["fm_contract_id"], ["__count"]
        )
        counts = {c.id: n for c, n in groups}
        for contract in self:
            contract.task_count = counts.get(contract.id, 0)

    @api.depends("visit_frequency", "asset_ids", "start_date", "end_date")
    def _compute_planned_visit_count(self):
        for contract in self:
            per_year = FREQUENCY_PER_YEAR.get(contract.visit_frequency, 12)
            years = 1.0
            if contract.start_date and contract.end_date and contract.end_date > contract.start_date:
                years = (contract.end_date - contract.start_date).days / 365.0
            contract.planned_visit_count = max(1, round(per_year * years)) * len(contract.asset_ids)

    # ------------------------------------------------------------------
    # Auto-scheduling
    # ------------------------------------------------------------------
    def _next_working_day(self, day):
        self.ensure_one()
        if self.skip_weekends:
            while day.weekday() >= 5:  # 5=Sat, 6=Sun
                day += timedelta(days=1)
        return day

    def _fsm_project(self):
        return self.env.ref("fm_fsm.fsm_project_fm", raise_if_not_found=False)

    def _generate_schedule(self, horizon_end=None):
        """Create planned (PPM) FSM tasks for every covered asset at the
        contract's frequency, from the contract start up to ``horizon_end``
        (default: the contract end). Idempotent — never double-books an asset
        on a day that already has a scheduled visit.
        """
        Task = self.env["project.task"]
        project = self._fsm_project()
        if not project:
            return Task
        stage_draft = self.env.ref("fm_fsm.fsm_stage_draft", raise_if_not_found=False)
        stage_assigned = self.env.ref("fm_fsm.fsm_stage_assigned", raise_if_not_found=False)
        created = Task
        for c in self:
            if not (c.asset_ids and c.visit_frequency and c.start_date and c.end_date):
                continue
            per_year = FREQUENCY_PER_YEAR.get(c.visit_frequency, 12)
            interval = max(1, round(365 / per_year))
            end = min(c.end_date, horizon_end or c.end_date)
            company = c.sale_order_id.company_id or self.env.company
            tech = c.preferred_technician_id
            tech_user = tech.user_id if tech and tech.user_id else False

            # Existing scheduled dates per asset, to stay idempotent.
            existing = {}
            for task in c.task_ids.filtered("date_deadline"):
                # date_deadline is a Datetime; compare on the date part so the
                # idempotency check matches the scheduled day.
                existing.setdefault(task.fm_asset_id.id, set()).add(task.date_deadline.date())

            vals_list = []
            for asset in c.asset_ids:
                day = c.start_date
                while day <= end:
                    sched_day = c._next_working_day(day)
                    if sched_day not in existing.setdefault(asset.id, set()):
                        # Title = customer/site so the calendar reads by client;
                        # asset & contract are in the description and FM fields.
                        visit_name = c.partner_id.display_name or asset.display_name
                        if asset.service_line:
                            visit_name = "%s — %s" % (
                                visit_name,
                                dict(asset._fields["service_line"].selection).get(
                                    asset.service_line, asset.service_line
                                ),
                            )
                        vals = {
                            "name": visit_name,
                            "project_id": project.id,
                            "company_id": company.id,
                            "partner_id": c.partner_id.id,
                            "fm_asset_id": asset.id,
                            "fm_contract_id": c.id,
                            "fm_wo_type": "ppm",
                            "fm_severity": "p3_medium",
                            "date_deadline": sched_day,
                            "description": _(
                                "Planned visit for %(asset)s under contract %(ref)s"
                            ) % {"asset": asset.display_name, "ref": c.contract_number},
                        }
                        if tech_user:
                            vals["user_ids"] = [(6, 0, [tech_user.id])]
                            if stage_assigned:
                                vals["stage_id"] = stage_assigned.id
                        elif stage_draft:
                            vals["stage_id"] = stage_draft.id
                        vals_list.append(vals)
                        existing[asset.id].add(sched_day)
                    day += timedelta(days=interval)
            if vals_list:
                created += Task.create(vals_list)
        return created

    def action_generate_visits(self):
        """Manual trigger: schedule the full remaining term now."""
        self.ensure_one()
        if not self.asset_ids:
            raise UserError(_("Add at least one covered asset before generating visits."))
        if not self.start_date or not self.end_date or self.end_date <= self.start_date:
            raise UserError(_("Set a valid start and end date on the contract first."))
        created = self._generate_schedule()
        self.message_post(body=_("%s planned Field Service visit(s) generated.") % len(created))
        return self.action_view_tasks()

    def action_view_tasks(self):
        self.ensure_one()
        project = self._fsm_project()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visits / Work Orders"),
            "res_model": "project.task",
            "view_mode": "calendar,list,kanban,form",
            "domain": [("fm_contract_id", "=", self.id)],
            "context": {
                "default_fm_contract_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_project_id": project.id if project else False,
            },
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
