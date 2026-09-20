# -*- coding: utf-8 -*-
import calendar
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# How many visits per asset per year for each cadence. Used for the planned
# count shown on the contract; the actual dates come from _fm_visit_dates.
FREQUENCY_PER_YEAR = {
    "weekly": 52,
    "fortnightly": 26,
    "twice_monthly": 24,
    "monthly": 12,
    "bi_monthly": 6,
    "quarterly": 4,
    "semi_annual": 2,
    "annual": 1,
}

# Cadences that step by CALENDAR MONTHS, not by a fixed number of days.
#
# A monthly AMC signed for the 19th must fall on the 19th of every month.
# Stepping by round(365/12)=30 days instead puts the third visit on the 18th
# and the twelfth on the 15th -- four days adrift by the end of a one-year
# contract, silently, on every recurring contract in the system.
FREQUENCY_MONTHS = {
    "monthly": 1,
    "bi_monthly": 2,
    "quarterly": 3,
    "semi_annual": 6,
    "annual": 12,
}

# Cadences that genuinely are a fixed number of days: a weekly visit belongs
# on the same weekday, which months do not preserve.
FREQUENCY_DAYS = {
    "weekly": 7,
    "fortnightly": 14,
}

# "Twice a month" is NOT fortnightly, and the difference is not cosmetic.
# The client's frequency table gives it as 24 visits a year on "two fixed
# dates per month"; a 14-day step gives 26 and the dates walk backwards
# through the month. A customer contracted for the 5th and the 20th would
# be visited on the 5th and 19th, then the 2nd and 16th, and so on. So it
# steps by calendar month like the monthly family, but lands twice.
TWICE_MONTHLY = "twice_monthly"

# Time-slot tagging. The client's process document requires that "every job
# carries exactly one time-slot tag" and shows the three slots on both the
# dashboard ("Today by Time Slot") and the technician's job list.
# Shared with sale.order.template, which offers the same cadences as a
# contract profile. One list, so a profile can never promise a frequency
# the generator does not implement.
FREQUENCY_SELECTION = [
    ("weekly", "Weekly"),
    ("fortnightly", "Every 2 Weeks"),
    ("twice_monthly", "Twice a Month"),
    ("monthly", "Monthly"),
    ("bi_monthly", "Every 2 Months"),
    ("quarterly", "Quarterly"),
    ("semi_annual", "Semi-Annual"),
    ("annual", "Annual"),
    ("custom", "Custom — enter interval"),
]

# The UAE weekend: Friday and Saturday (Python weekday() 4 and 5).
# Sunday is a working day -- a contract can legitimately be visited every
# Sunday, and treating it as a weekend silently moved every such visit to
# the Monday.
WEEKEND_DAYS = (4, 5)

WEEKDAYS = [
    ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"), ("3", "Thursday"),
    ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
]

TIME_SLOTS = [
    ("morning", "Morning"),
    ("day", "Day"),
    ("night", "Night"),
]

# Start time each slot schedules at. Taken from the technician screen in that
# document, which shows Morning 08:00, Day 13:00, Night 21:00.
SLOT_START_HOUR = {
    "morning": 8.0,
    "day": 13.0,
    "night": 21.0,
}

# Where one slot ends and the next begins. The document names the slots and
# their start times but never the boundaries, so these are ours: they are the
# widest reading that keeps each published start time inside its own slot.
# Recorded in CLAUDE.md section 4 with the rest of the unconfirmed behaviour.
SLOT_UPPER_HOUR = [
    (12.0, "morning"),
    (18.0, "day"),
]


def slot_for_hour(hour):
    """Which slot an hour of the day falls in."""
    for upper, slot in SLOT_UPPER_HOUR:
        if hour < upper:
            return slot
    return "night"


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
        FREQUENCY_SELECTION,
        string="Visit Frequency",
        default="monthly",
    )
    custom_interval_days = fields.Integer(
        string="Custom Interval (days)",
        help="Used when Visit Frequency is 'Custom' — number of days between "
             "visits for each covered asset, e.g. 45 for a 45-day cadence that "
             "doesn't fit the preset options.",
    )
    # The two dates for "Twice a Month". The client's table calls them "two
    # fixed dates per month" -- fixed meaning chosen per contract, not
    # derived, so these are plain inputs with a workable default rather than
    # something computed from the start date behind the user's back.
    visit_day_1 = fields.Integer(
        string="1st Visit Day",
        default=1,
        help="Day of the month for the first of the two monthly visits. "
             "A day later than the month has (say the 31st in February) "
             "falls on the last day of that month.",
    )
    visit_day_2 = fields.Integer(
        string="2nd Visit Day",
        default=15,
        help="Day of the month for the second of the two monthly visits.",
    )

    @api.constrains("visit_frequency", "visit_day_1", "visit_day_2")
    def _check_fm_twice_monthly_days(self):
        """Two real, different days -- caught here rather than in the form.

        A contract imported or written over RPC with both days the same
        would quietly schedule twelve visits a year on a cadence sold as
        twenty-four, and nothing downstream would notice.
        """
        for record in self:
            if record.visit_frequency != TWICE_MONTHLY:
                continue
            for day in (record.visit_day_1, record.visit_day_2):
                if not 1 <= day <= 31:
                    raise ValidationError(_(
                        "A twice-monthly visit day must be between 1 and 31; "
                        "got %s.", day))
            if record.visit_day_1 == record.visit_day_2:
                raise ValidationError(_(
                    "Twice a month needs two different days of the month. "
                    "Both are set to %s, which is once a month.",
                    record.visit_day_1))

    @api.onchange("visit_frequency")
    def _onchange_fm_twice_monthly_days(self):
        """Start the two days from the contract's own start date.

        Only a suggestion, and only when the fields are still at their
        defaults: the client chose the phrase "fixed dates", so the person
        writing the contract has the last word.
        """
        for record in self:
            if record.visit_frequency != TWICE_MONTHLY:
                continue
            if (record.visit_day_1, record.visit_day_2) != (1, 15):
                continue
            start = record._fm_term()[0]
            if not start:
                continue
            record.visit_day_1 = start.day
            # A fortnight on, wrapped inside a 28-day month so the second
            # visit cannot land in the next one.
            record.visit_day_2 = ((start.day + 13) % 28) + 1

    fm_visit_weekday = fields.Selection(
        WEEKDAYS,
        string="Visits On",
        help="For a weekly or fortnightly contract, the day of the week the "
             "customer is visited. Left blank, the day is taken from the "
             "contract start date -- which is whenever the contract happened "
             "to be signed, not necessarily the day anyone agreed to.",
    )
    skip_weekends = fields.Boolean(
        string="Skip Weekends (Fri/Sat)",
        default=True,
        help="Push visits that fall on Friday or Saturday to the next "
             "working day. Sunday is a working day in the UAE.",
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
    fm_time_slot = fields.Selection(
        TIME_SLOTS,
        string="Visit Time Slot",
        default="morning",
        help="Slot generated visits are scheduled in. Choosing a slot fills in "
             "the start time below; the time stays editable for a contract "
             "that needs a precise hour.",
    )
    visit_start_time = fields.Float(
        string="Default Visit Start Time",
        default=8.0,
        help="Time of day (24h) auto-scheduled visits are planned to start, e.g. 9.0 = 09:00.",
    )
    visit_duration_hours = fields.Float(
        string="Default Visit Duration (hours)",
        default=2.0,
    )

    @api.onchange("fm_time_slot")
    def _onchange_fm_time_slot(self):
        """Picking a slot fills in its start time.

        One source of truth for *when* a visit happens: the time. The slot is
        the label, and on the visit itself it is derived back from the time,
        so a dispatcher who reschedules a job cannot leave a stale tag behind.
        """
        for record in self:
            if record.fm_time_slot:
                record.visit_start_time = SLOT_START_HOUR[record.fm_time_slot]

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
        when Visit Frequency is set to 'Custom' instead of a preset cadence.

        Only meaningful for the day-based cadences and 'custom'. The monthly
        family does not have a constant day interval -- use _fm_visit_dates
        for the actual schedule.
        """
        self.ensure_one()
        if self.visit_frequency == "custom":
            return max(1, self.custom_interval_days or 30)
        if self.visit_frequency in FREQUENCY_DAYS:
            return FREQUENCY_DAYS[self.visit_frequency]
        per_year = FREQUENCY_PER_YEAR.get(self.visit_frequency, 12)
        return max(1, round(365 / per_year))

    @staticmethod
    def _fm_add_months(anchor, months):
        """``anchor`` shifted by whole months, clamped to the month's length.

        Anchored on the contract start, never on the previous visit: stepping
        month-by-month from a clamped date walks the schedule backwards (31
        Jan -> 28 Feb -> 28 Mar -> ...), while anchoring keeps 31 Jan -> 28
        Feb -> 31 Mar, which is what a contract for "the 31st" means.

        Clamping short months to their last day is the reading the client's
        process document itself suggests ("e.g. move to last day of month")
        but lists as still to confirm -- see the module README.
        """
        total = anchor.month - 1 + months
        year = anchor.year + total // 12
        month = total % 12 + 1
        return anchor.replace(
            year=year, month=month,
            day=min(anchor.day, calendar.monthrange(year, month)[1]),
        )

    def _fm_visit_dates(self, start, end):
        """Every visit date from ``start`` to ``end`` inclusive, at this
        contract's cadence. Calendar-stepped for the monthly family, day-
        stepped for weekly/fortnightly/custom."""
        self.ensure_one()
        if self.visit_frequency == TWICE_MONTHLY:
            return self._fm_twice_monthly_dates(start, end)
        months = FREQUENCY_MONTHS.get(self.visit_frequency)
        dates = []
        if months:
            occurrence = 0
            while True:
                day = self._fm_add_months(start, months * occurrence)
                if day > end:
                    break
                dates.append(day)
                occurrence += 1
                if occurrence > 1200:  # a 100-year monthly contract; bail out
                    break
        else:
            interval = timedelta(days=self._visit_interval_days())
            day = self._fm_first_day_of_series(start)
            while day <= end:
                dates.append(day)
                day += interval
        return dates

    def _fm_day_is_chosen(self):
        """Whether this cadence names the day, rather than landing on one.

        Weekly and fortnightly repeat on a weekday: "every Sunday" is the
        agreement. The monthly family repeats on a date -- the 19th -- and
        which weekday that is drifts month to month. The distinction
        decides whether the weekend rule may move a visit: it may move a
        date that happened to land on a Friday, and it may not move a day
        the customer chose.
        """
        self.ensure_one()
        return self.visit_frequency in FREQUENCY_DAYS

    def _fm_first_day_of_series(self, start):
        """Where a day-stepped series begins.

        ``fm_visit_weekday`` set: the first such weekday on or after the
        term start, so "every Sunday" means Sundays whatever day the
        contract was signed. Left blank the series starts on the term
        start, which is what it has always done.
        """
        self.ensure_one()
        if not (self._fm_day_is_chosen() and self.fm_visit_weekday):
            return start
        wanted = int(self.fm_visit_weekday)
        return start + timedelta(days=(wanted - start.weekday()) % 7)

    def _fm_twice_monthly_days(self):
        """The two chosen days, ordered, ignoring anything out of range."""
        self.ensure_one()
        days = {d for d in (self.visit_day_1, self.visit_day_2) if 1 <= d <= 31}
        return sorted(days) or [1]

    def _fm_twice_monthly_dates(self, start, end):
        """Both chosen days in every month the term touches.

        Walks whole months rather than stepping by days, so the dates stay
        put: the client's table asks for 24 visits a year on two fixed
        dates, and a 14-day step drifts them backwards through the month.

        A day the month does not have falls on its last day, matching the
        monthly family. When both days clamp onto that same last day -- the
        30th and 31st in February -- it is one visit, not two booked on top
        of each other.
        """
        self.ensure_one()
        days = self._fm_twice_monthly_days()
        dates = []
        month = start.replace(day=1)
        guard = 0
        while month <= end:
            last = calendar.monthrange(month.year, month.month)[1]
            for day in days:
                visit = month.replace(day=min(day, last))
                if start <= visit <= end and visit not in dates:
                    dates.append(visit)
            month = self._fm_add_months(month, 1)
            guard += 1
            if guard > 1200:  # a 100-year contract; bail out
                break
        return sorted(dates)

    def _fm_planned_visit_count(self):
        """How many visits the current settings would produce over the term."""
        self.ensure_one()
        start, end = self._fm_term()
        if not start or not end or end <= start:
            return max(1, len(self._fm_covered_assets()))
        return max(1, len(self._fm_visit_dates(start, end))) * len(
            self._fm_covered_assets())

    def _next_working_day(self, day):
        """Move a visit off the weekend -- which in the UAE is Fri/Sat.

        This skipped Sat/Sun until it was caught against the client's own
        schedule: a contract visited every Sunday had every single visit
        pushed to Monday, silently, because Python's weekday() makes
        Sunday 6 and the test was ``>= 5``. Sunday is an ordinary working
        day here; Friday is not.
        """
        self.ensure_one()
        if self._fm_day_is_chosen():
            # The weekday IS the agreement. A customer contracted for every
            # Friday gets Fridays; moving them would quietly rewrite the
            # contract, which is the same mistake in the other direction.
            return day
        if self.skip_weekends:
            while day.weekday() in WEEKEND_DAYS:
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
            end = min(term_end, horizon_end or term_end)
            visit_dates = contract._fm_visit_dates(start, end)
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
                for day in visit_dates:
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
