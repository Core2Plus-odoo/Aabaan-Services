# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import _, fields, models
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


class FmVisitScheduleMixin(models.AbstractModel):
    """Contract-driven visit scheduling on native Field Service.

    **There is one generator.** This whole consolidation exists because two
    things were writing ``project.task`` for the same customer's visits, so
    shipping a second copy of the generator — one for contracts written in
    Sales, one for the legacy ``fm.contract`` — would have recreated the
    problem it is meant to end. Both models use this one.

    What differs between them is only the *names* of the fields it reads:
    a sale order calls its covered assets ``fm_asset_ids`` and its term
    ``fm_start_date`` / ``fm_end_date``, where ``fm.contract`` calls them
    ``asset_ids``, ``start_date`` and ``end_date``. Each concrete model
    answers a handful of small accessors below and the scheduling itself is
    written once. When ``fm.contract`` goes, the accessors on it go with it
    and nothing here changes.

    Visits are native FSM tasks (``project.task`` in the FM Field Service
    project), so they inherit planning, the calendar, mobile worksheets,
    timesheets and billing rather than reimplementing any of it.
    """

    _name = "fm.visit.schedule.mixin"
    _description = "FM Contract Visit Scheduling"

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
            ("custom", "Custom — enter interval"),
        ],
        string="Visit Frequency",
        default="monthly",
    )
    custom_interval_days = fields.Integer(
        string="Custom Interval (days)",
        help="Used when Visit Frequency is 'Custom' — number of days between "
             "visits for each covered asset, e.g. 45 for a 45-day cadence that "
             "doesn't fit the preset options.",
    )
    skip_weekends = fields.Boolean(
        string="Skip Weekends",
        default=True,
        help="Push visits that fall on Sat/Sun to the next working day.",
    )
    preferred_technician_id = fields.Many2one("hr.employee", string="Preferred Technician")
    auto_schedule_state = fields.Selection(
        [
            ("draft", "Draft — needs review before dispatch"),
            ("confirmed", "Confirmed — ready to assign/dispatch"),
        ],
        string="Auto-scheduled Visits Start As",
        default="confirmed",
        help="Stage new auto-generated visits open in. 'Confirmed' puts them "
             "straight in the Assigned stage (technician set if a Preferred "
             "Technician is chosen); 'Draft' holds them for dispatcher review "
             "before anyone is assigned.",
    )
    visit_start_time = fields.Float(
        string="Default Visit Start Time",
        default=9.0,
        help="Time of day (24h) auto-scheduled visits are planned to start, e.g. 9.0 = 09:00.",
    )
    visit_duration_hours = fields.Float(
        string="Default Visit Duration (hours)",
        default=2.0,
    )

    # ------------------------------------------------------------------
    # What each concrete model has to answer
    # ------------------------------------------------------------------
    def _fm_covered_assets(self):
        """The fm.asset records this contract covers."""
        raise NotImplementedError

    def _fm_term(self):
        """(start_date, end_date) of the contract."""
        raise NotImplementedError

    def _fm_contract_ref(self):
        """Human reference printed into each visit's description."""
        raise NotImplementedError

    def _fm_visit_link_vals(self):
        """The project.task field(s) that point a visit back at this
        contract, as a values dict."""
        raise NotImplementedError

    def _fm_company(self):
        """Company the generated visits belong to."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Cadence
    # ------------------------------------------------------------------
    def _visit_interval_days(self):
        """Days between visits for one asset, honouring a custom interval
        when Visit Frequency is set to 'Custom' instead of a preset cadence."""
        self.ensure_one()
        if self.visit_frequency == "custom":
            return max(1, self.custom_interval_days or 30)
        per_year = FREQUENCY_PER_YEAR.get(self.visit_frequency, 12)
        return max(1, round(365 / per_year))

    def _fm_planned_visit_count(self):
        """How many visits the current settings would produce over the term."""
        self.ensure_one()
        interval = self._visit_interval_days()
        start, end = self._fm_term()
        years = 1.0
        if start and end and end > start:
            years = (end - start).days / 365.0
        visits_per_year = 365.0 / interval
        return max(1, round(visits_per_year * years)) * len(self._fm_covered_assets())

    def _next_working_day(self, day):
        self.ensure_one()
        if self.skip_weekends:
            while day.weekday() >= 5:  # 5=Sat, 6=Sun
                day += timedelta(days=1)
        return day

    def _fsm_project(self):
        return self.env.ref("fm_fsm.fsm_project_fm", raise_if_not_found=False)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
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
        # fm.asset.service_line is a related field, so _fields[...].selection is
        # not the static option list (it's resolved lazily) — fetch the
        # display labels via fields_get() instead of dict()-ing .selection.
        service_line_labels = dict(
            self.env["fm.asset"].fields_get(["service_line"])["service_line"]["selection"]
        )
        created = Task
        for contract in self:
            assets = contract._fm_covered_assets()
            start, term_end = contract._fm_term()
            if not (assets and contract.visit_frequency and start and term_end):
                continue
            interval = contract._visit_interval_days()
            end = min(term_end, horizon_end or term_end)
            company = contract._fm_company()
            link_vals = contract._fm_visit_link_vals()
            contract_ref = contract._fm_contract_ref()
            tech = contract.preferred_technician_id
            tech_user = tech.user_id if tech and tech.user_id else False

            # Existing scheduled dates per asset, to stay idempotent.
            existing = {}
            for task in contract.fm_task_ids.filtered("date_deadline"):
                # date_deadline is a Datetime; compare on the date part so the
                # idempotency check matches the scheduled day.
                existing.setdefault(task.fm_asset_id.id, set()).add(task.date_deadline.date())

            vals_list = []
            end_dt_list = []
            for asset in assets:
                day = start
                while day <= end:
                    sched_day = contract._next_working_day(day)
                    if sched_day not in existing.setdefault(asset.id, set()):
                        # Title = customer/site so the calendar reads by client;
                        # asset & contract are in the description and FM fields.
                        visit_name = contract.partner_id.display_name or asset.display_name
                        if asset.service_line:
                            visit_name = "%s — %s" % (
                                visit_name,
                                service_line_labels.get(
                                    asset.service_line, asset.service_line
                                ),
                            )
                        # Planned date = the visit date itself, at the contract's
                        # default visit start time/duration, so the task appears
                        # on the FSM planning Gantt and mobile "Today" view (which
                        # key on planned_date_begin/date_end), not just the
                        # calendar (which keys on date_deadline).
                        # date_deadline must be >= planned_date_begin (a project.task
                        # constraint) — use the visit's end time, not midnight of the
                        # day, or task creation is rejected ("planned start date must
                        # be before planned end date").
                        duration = contract.visit_duration_hours or 2.0
                        start_dt = datetime.combine(sched_day, datetime.min.time()) + timedelta(
                            hours=contract.visit_start_time or 9.0
                        )
                        end_dt = start_dt + timedelta(hours=duration)
                        vals = {
                            "name": visit_name,
                            "project_id": project.id,
                            "company_id": company.id,
                            "partner_id": contract.partner_id.id,
                            "fm_asset_id": asset.id,
                            "fm_wo_type": "ppm",
                            "fm_severity": "p3_medium",
                            "date_deadline": end_dt,
                            "planned_date_begin": start_dt,
                            # date_end is NOT set here: on this build it is
                            # silently discarded when passed to create() (a
                            # write() right after create() is the only way it
                            # sticks) — set in the follow-up loop below.
                            "allocated_hours": duration,
                            "description": _(
                                "Planned visit for %(asset)s under contract %(ref)s"
                            ) % {"asset": asset.display_name, "ref": contract_ref},
                        }
                        vals.update(link_vals)
                        if tech_user:
                            vals["user_ids"] = [(6, 0, [tech_user.id])]
                        # Initial stage follows the contract's explicit choice —
                        # 'confirmed' visits go straight to Assigned (ready to
                        # dispatch, whether or not a technician is set yet);
                        # 'draft' holds them for dispatcher review.
                        if contract.auto_schedule_state == "draft" and stage_draft:
                            vals["stage_id"] = stage_draft.id
                        elif stage_assigned:
                            vals["stage_id"] = stage_assigned.id
                        vals_list.append(vals)
                        end_dt_list.append(end_dt)
                        existing[asset.id].add(sched_day)
                    day += timedelta(days=interval)
            if vals_list:
                new_tasks = Task.create(vals_list)
                for task, task_end_dt in zip(new_tasks, end_dt_list):
                    task.date_end = task_end_dt
                created += new_tasks
        return created

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def _fm_visit_context(self):
        project = self._fsm_project()
        context = {
            "default_%s" % key: value
            for key, value in self._fm_visit_link_vals().items()
        }
        context["default_partner_id"] = self.partner_id.id
        context["default_project_id"] = project.id if project else False
        return context

    def action_generate_visits(self):
        """Manual trigger: schedule the full remaining term now."""
        self.ensure_one()
        start, end = self._fm_term()
        if not self._fm_covered_assets():
            raise UserError(_("Add at least one covered asset before generating visits."))
        if not start or not end or end <= start:
            raise UserError(_("Set a valid start and end date on the contract first."))
        created = self._generate_schedule()
        self.message_post(body=_("%s planned Field Service visit(s) generated.") % len(created))
        if not created:
            raise UserError(_(
                "No new visits were generated — every covered asset already has a "
                "scheduled visit for every date in this window. Check the Visits / "
                "Work Orders smart button for the existing schedule."
            ))
        # Open scoped to exactly the batch just created, not the contract's
        # full visit history — otherwise a new run's visits get buried among
        # everything already generated and it looks like nothing happened.
        return {
            "type": "ir.actions.act_window",
            "name": _("%s Visit(s) Generated") % len(created),
            "res_model": "project.task",
            "view_mode": "list,calendar,kanban,form",
            "domain": [("id", "in", created.ids)],
            "context": self._fm_visit_context(),
        }

    def action_view_tasks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visits / Work Orders"),
            "res_model": "project.task",
            "view_mode": "calendar,list,kanban,form",
            "domain": [("id", "in", self.fm_task_ids.ids)],
            "context": self._fm_visit_context(),
        }
