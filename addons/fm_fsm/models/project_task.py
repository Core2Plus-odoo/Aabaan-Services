# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.fm_contract.models.fm_sla_rule import SEVERITY
from odoo.addons.fm_fsm.models.fm_visit_schedule_mixin import (
    TIME_SLOTS,
    slot_for_hour,
)


# How far out an automatic follow-up is booked. The client's process
# document calls this "the 3-day rule"; it is one place so a change to it is
# one edit rather than a search.
FOLLOWUP_DAYS = 3

# The context key the guarded-flow buttons set on their own writes. Without
# it the interception in write() would refuse the very transitions the
# buttons exist to make.
GUARD_BYPASS = "fm_visit_guard_bypass"


class ProjectTask(models.Model):
    """Facility Management fields grafted onto the native Field Service task.

    Standard-first re-base: work orders are executed as native FSM tasks
    (``project.task`` with ``is_fsm=True``). This ``_inherit`` adds the FM
    domain context — the asset being serviced, its contract, severity and
    service line — without a bespoke state machine. Stage/scheduling/SLA are
    handled by native Field Service, SLA policies and recurrence.
    """

    _inherit = "project.task"

    fm_asset_id = fields.Many2one(
        "fm.asset",
        string="Asset",
        index=True,
        tracking=True,
        help="Facility asset this job services.",
    )
    # "Asset Service Line", not "Service Line": this database also carries a
    # manual x_service_line on project.task with that label, and Odoo warns
    # about the clash at every registry load. This one is the asset's, which
    # is the more precise name anyway.
    fm_service_line = fields.Selection(
        related="fm_asset_id.service_line", store=True, index=True,
        string="Asset Service Line",
    )
    fm_location_id = fields.Many2one(
        related="fm_asset_id.location_fm_id", store=True, string="Asset Location"
    )
    fm_contract_order_id = fields.Many2one(
        "sale.order",
        string="AMC Contract",
        index=True,
        tracking=True,
        domain="[('is_fm_contract', '=', True)]",
        help="The contract this visit belongs to. A contract is a sale "
             "order, so this is the order the customer agreed to.",
    )
    # Deliberately NOT project.task.sale_order_id: that native field means
    # "the order this task bills to", derived from the sale order line that
    # created the task, and it is computed. A visit generated from an AMC
    # contract is not necessarily billed from a line on that order, so the
    # two answers can differ and only one of them is the contract.
    fm_severity = fields.Selection(
        SEVERITY, string="Severity", default="p3_medium", tracking=True, index=True
    )
    fm_time_slot = fields.Selection(
        TIME_SLOTS,
        string="Time Slot",
        compute="_compute_fm_time_slot",
        store=True,
        index=True,
        help="Morning, Day or Night, derived from the planned start time.",
    )
    fm_wo_type = fields.Selection(
        [
            ("reactive", "Reactive"),
            ("ppm", "PPM / Planned"),
            ("compliance", "Compliance"),
            ("project", "Project"),
            ("inspection", "Inspection"),
        ],
        string="Work Type",
        default="reactive",
        tracking=True,
    )

    def _fm_contract_order(self):
        """The sale order behind this visit's contract.

        One link now that the legacy ``fm.contract`` is gone. Kept as a
        method rather than inlined at the call sites: callers want "the
        contract's order", and this is where a second answer would go if
        one ever comes back.
        """
        self.ensure_one()
        return self.fm_contract_order_id

    @api.onchange("fm_contract_order_id")
    def _onchange_fm_contract_order_id(self):
        """Pull the customer from the contract's sale order."""
        for task in self:
            if task.fm_contract_order_id and task.fm_contract_order_id.partner_id:
                task.partner_id = task.fm_contract_order_id.partner_id

    # ------------------------------------------------------------------
    # Guard-railed execution (consolidation plan P1)
    #
    # Ported from aabaan_field_ops on the retired build. Two things are
    # deliberately different from the source:
    #
    # * Stages are resolved by **xmlid**, not by matching stage names
    #   case-insensitively. On the source build the FSM stages were data
    #   somebody had typed into the database, so name hints were the only
    #   handle available. Here they are module records in
    #   data/fsm_stages.xml, and a rename in the UI must not silently stop
    #   the guards working.
    # * Completing a visit with no service document attached sends it to
    #   **Pending Documents**, not to an error. That stage exists for
    #   exactly this case -- the work is finished, the paperwork is not --
    #   and the source build had no equivalent, so it had nowhere to put
    #   an honest half-done job.
    # ------------------------------------------------------------------
    fm_is_fsm = fields.Boolean(
        string="Field Service Visit",
        related="project_id.is_fsm",
        store=False,
        help="Technical: whether this task lives in a Field Service project. "
             "Declared here rather than reading industry_fsm's own is_fsm in "
             "the view, because a view naming a field the model does not have "
             "fails to load — and that is a red build, not a warning. "
             "project.project.is_fsm is the field this platform already relies "
             "on (fm_fsm/data/fsm_project.xml sets it).",
    )
    fm_visit_started_at = fields.Datetime(
        string="Check-in", readonly=True, copy=False, tracking=True,
        help="Stamped by the Start Visit button. Not editable: it is the "
             "evidence of when somebody was actually on site.",
    )
    fm_visit_completed_at = fields.Datetime(
        string="Check-out", readonly=True, copy=False, tracking=True,
        help="Stamped by the Complete Visit button.",
    )
    fm_visit_duration_actual = fields.Float(
        string="Time on Site (hours)",
        compute="_compute_fm_visit_duration_actual",
        help="Check-out minus check-in. Blank until both are stamped — an "
             "unfinished visit has no duration, and showing zero would read "
             "as a job nobody spent any time on.",
    )
    fm_infestation_found = fields.Boolean(
        string="Infestation Found",
        help="Tick before completing. A follow-up visit is then raised "
             "automatically on completion — three days out, and unbilled.",
    )
    fm_treatment_summary = fields.Text(
        string="Treatment Carried Out",
        help="Required before the visit can be completed: the areas treated "
             "and the work done. This is what the municipality return is "
             "written from.",
    )
    fm_chemicals_used = fields.Text(
        string="Chemicals / Materials Used",
        help="Product and quantity, as the municipality return requires.",
    )
    fm_cancel_reason = fields.Text(
        string="Cancellation Reason", copy=False,
        help="Required before a visit can be cancelled — a cancelled visit "
             "has to be explainable to the customer who was expecting it.",
    )
    fm_followup_task_id = fields.Many2one(
        "project.task", string="Follow-up Raised", readonly=True, copy=False,
        help="The follow-up visit this one raised automatically.",
    )
    fm_followup_origin_id = fields.Many2one(
        "project.task", string="Follow-up To", readonly=True, copy=False,
        help="The visit that raised this follow-up.",
    )
    fm_sla_escalated = fields.Boolean(
        string="Escalated", readonly=True, copy=False,
        help="Set once the daily watchdog has raised an activity for this "
             "visit, so nobody is chased twice for the same job.",
    )

    @api.depends("fm_visit_started_at", "fm_visit_completed_at")
    def _compute_fm_visit_duration_actual(self):
        for task in self:
            if task.fm_visit_started_at and task.fm_visit_completed_at:
                delta = task.fm_visit_completed_at - task.fm_visit_started_at
                task.fm_visit_duration_actual = round(delta.total_seconds() / 3600.0, 2)
            else:
                task.fm_visit_duration_actual = 0.0

    fm_has_service_document = fields.Boolean(
        string="Service Document Attached",
        compute="_compute_fm_has_service_document",
        search="_search_fm_has_service_document",
        help="Whether a photo or signed service report has been attached to "
             "this visit.",
    )

    def _compute_fm_has_service_document(self):
        """True once anything is attached to the visit.

        Deliberately any attachment, not a bespoke field: the FSM mobile app,
        the chatter and the worksheet report all land in ir.attachment
        against the task, and a technician photographing a job should not
        have to care which route the file took.
        """
        if not self.ids:
            for task in self:
                task.fm_has_service_document = False
            return
        counts = dict(
            self.env["ir.attachment"]._read_group(
                [("res_model", "=", "project.task"), ("res_id", "in", self.ids)],
                groupby=["res_id"],
                aggregates=["__count"],
            )
        )
        for task in self:
            task.fm_has_service_document = bool(counts.get(task.id))

    def _search_fm_has_service_document(self, operator, value):
        """Make the field filterable.

        A computed field with no store= cannot be searched without this, and
        the "Awaiting Documents" filter is the whole point of the flag: it is
        how the dispatcher finds the visits the client's dashboard counts as
        "jobs awaiting documents".
        """
        if operator not in ("=", "!="):
            raise UserError(_("Unsupported filter on Service Document Attached."))
        with_document = [
            row[0] for row in self.env["ir.attachment"]._read_group(
                [("res_model", "=", "project.task")],
                groupby=["res_id"],
                aggregates=["__count"],
            )
        ]
        wants_document = bool(value) if operator == "=" else not value
        return [("id", "in" if wants_document else "not in", with_document)]

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------
    def _fm_stage(self, xmlid):
        """A stage by xmlid, or an empty recordset.

        By xmlid and not by name: the stages are module records, and a
        business renaming "In Progress" in the UI must not quietly switch
        the execution guards off.
        """
        return self.env.ref("fm_fsm.%s" % xmlid, raise_if_not_found=False)

    def _fm_is_guarded_visit(self):
        """Whether the execution guards apply to this task.

        They apply to FM visits, not to every task that happens to live in
        a Field Service project: an imported record, demo data or another
        team's FSM job must not suddenly need a treatment summary to close.
        A task in the FM project is ours by definition; one elsewhere is
        ours if it carries a contract or an asset.
        """
        self.ensure_one()
        if not self.project_id.is_fsm:
            return False
        fm_project = self.env.ref("fm_fsm.fsm_project_fm", raise_if_not_found=False)
        if fm_project and self.project_id == fm_project:
            return True
        return bool(self.fm_contract_order_id or self.fm_asset_id)

    # ------------------------------------------------------------------
    # Guard-railed execution
    # ------------------------------------------------------------------
    def action_fm_start_visit(self):
        """Check the technician in, and move the visit to In Progress."""
        now = fields.Datetime.now()
        for task in self:
            if task.fm_visit_started_at:
                raise UserError(_(
                    "%s was already started at %s.",
                    task.display_name, task.fm_visit_started_at))
            if not task.user_ids:
                raise UserError(_(
                    "Assign a technician to \"%s\" before starting the visit "
                    "— a check-in with nobody checked in proves nothing.",
                    task.display_name))
            vals = {"fm_visit_started_at": now}
            stage = task._fm_stage("fsm_stage_in_progress")
            if stage:
                vals["stage_id"] = stage.id
            task.with_context(**{GUARD_BYPASS: True}).write(vals)
        return True

    def action_fm_complete_visit(self):
        """Check the technician out, raise any follow-up, and pick the stage.

        The stage is Completed when a service document is attached and
        Pending Documents when it is not. Refusing to complete would be the
        easy implementation and the wrong one: the work really is finished,
        and a visit stuck in In Progress says a technician is still on site.
        """
        now = fields.Datetime.now()
        for task in self:
            if not task.fm_visit_started_at:
                raise UserError(_(
                    "Start the visit first — \"%s\" has no check-in.",
                    task.display_name))
            if task.fm_visit_completed_at:
                raise UserError(_(
                    "%s was already completed at %s.",
                    task.display_name, task.fm_visit_completed_at))
            if not (task.fm_treatment_summary or "").strip():
                raise UserError(_(
                    "Fill in \"Treatment Carried Out\" on the Field Report tab "
                    "of \"%s\" before completing it — the municipality return "
                    "is written from that field.",
                    task.display_name))

            vals = {"fm_visit_completed_at": now}
            notes = [_("Visit completed — %s on site.",
                       task.user_ids[:1].name or self.env.user.name)]

            if task.fm_infestation_found and not task.fm_followup_task_id:
                followup = task._fm_create_followup_visit()
                if followup:
                    vals["fm_followup_task_id"] = followup.id
                    notes.append(_(
                        "Infestation found — follow-up visit \"%(name)s\" raised "
                        "automatically for %(date)s. It is unbilled.",
                        name=followup.display_name,
                        date=followup.date_deadline and followup.date_deadline.date() or "",
                    ))

            stage = (task._fm_stage("fsm_stage_completed")
                     if task.fm_has_service_document
                     else task._fm_stage("fsm_stage_pending_docs"))
            if stage:
                vals["stage_id"] = stage.id
            if not task.fm_has_service_document:
                notes.append(_(
                    "No service document attached, so this visit is in Pending "
                    "Documents. Attach the site photo or signed report to close it."))

            task.with_context(**{GUARD_BYPASS: True}).write(vals)
            task.message_post(body="\n".join(notes))
        return True

    def action_fm_cancel_visit(self):
        """Cancel the visit, with the reason already on the record."""
        for task in self:
            if not (task.fm_cancel_reason or "").strip():
                raise UserError(_(
                    "Give a cancellation reason on the Field Report tab of "
                    "\"%s\" first — a customer who was expecting a visit is "
                    "owed an explanation.",
                    task.display_name))
            vals = {}
            stage = task._fm_stage("fsm_stage_cancelled")
            if stage:
                vals["stage_id"] = stage.id
            task.with_context(**{GUARD_BYPASS: True}).write(vals)
            task.message_post(body=_("Visit cancelled: %s", task.fm_cancel_reason))
        return True

    def _fm_create_followup_visit(self):
        """The unbilled follow-up, three days out.

        Unbilled means exactly one thing on this platform: no products are
        put on the task. ``industry_fsm_sale`` bills a visit from the
        products recorded against it, so a task carrying none invoices
        nothing — there is no flag to set and none is invented here.

        Copied from this visit rather than generated from the contract: a
        follow-up is to the same site, the same asset and the same
        technician, on a date the contract's cadence knows nothing about.
        """
        self.ensure_one()
        start = (self.fm_visit_completed_at or fields.Datetime.now()) + timedelta(
            days=FOLLOWUP_DAYS)
        duration = self.allocated_hours or 2.0
        vals = {
            "name": _("Follow-up — %s", self.name or ""),
            "project_id": self.project_id.id,
            "company_id": self.company_id.id or self.env.company.id,
            "partner_id": self.partner_id.id,
            "fm_asset_id": self.fm_asset_id.id,
            "fm_contract_order_id": self.fm_contract_order_id.id,
            "fm_service_line": self.fm_service_line,
            "fm_wo_type": "reactive",
            "fm_severity": self.fm_severity,
            "fm_followup_origin_id": self.id,
            "planned_date_begin": start,
            "date_deadline": start + timedelta(hours=duration),
            "allocated_hours": duration,
            "description": _(
                "Automatic follow-up to %(origin)s — infestation was found on "
                "that visit. Unbilled: no products are recorded against this "
                "task, so it invoices nothing.",
                origin=self.display_name),
        }
        if self.user_ids:
            vals["user_ids"] = [(6, 0, self.user_ids.ids)]
        stage = self._fm_stage("fsm_stage_assigned") or self._fm_stage("fsm_stage_draft")
        if stage:
            vals["stage_id"] = stage.id
        followup = self.with_context(**{GUARD_BYPASS: True}).create(vals)
        # date_end is silently discarded when passed inside create() on this
        # build -- a write() straight after is the only way it sticks. Same
        # quirk the generator works around; see CLAUDE.md section 4.
        followup.date_end = vals["date_deadline"]
        return followup

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def write(self, vals):
        """Two guards, both in write() rather than in the view.

        The client's process document asks for the document rule to be
        "enforced in the system logic, not optional for any user role", and
        the same reasoning covers the execution flow: a rule that only
        exists in a form is not a rule, because the kanban, the mobile app,
        an import and RPC all go round it.

        Order matters. The execution guard runs first: told to drag a visit
        straight to Completed, "use the Complete Visit button, it records
        the field report" is more use to a technician than "attach a
        document", even though both are true.
        """
        stage_id = vals.get("stage_id")
        if stage_id and not self.env.context.get(GUARD_BYPASS):
            self._fm_check_stage_jump(stage_id, vals)
        if stage_id:
            stage = self.env["project.task.type"].browse(stage_id)
            if stage.fm_requires_document:
                blocked = self.filtered(
                    lambda task: task.stage_id.id != stage_id
                    and not task.fm_has_service_document
                )
                if blocked:
                    raise UserError(_(
                        "These visits cannot be marked \"%(stage)s\" yet — no "
                        "service document is attached:\n\n%(visits)s\n\n"
                        "Attach the site photo or the signed service report "
                        "first. Until then the visit belongs in Pending "
                        "Documents.",
                        stage=stage.name,
                        visits="\n".join("• %s" % task.display_name for task in blocked),
                    ))
        return super().write(vals)

    def _fm_check_stage_jump(self, stage_id, vals):
        """Refuse a stage change that skips the guarded flow.

        Only for the three stages the buttons own. Everything else — Draft,
        Assigned, Acknowledged, Pending Documents, Signed Off — a dispatcher
        may still set freely, because nothing about those depends on
        evidence being captured first.
        """
        in_progress = self._fm_stage("fsm_stage_in_progress")
        completed = self._fm_stage("fsm_stage_completed")
        cancelled = self._fm_stage("fsm_stage_cancelled")
        for task in self:
            if task.stage_id.id == stage_id or not task._fm_is_guarded_visit():
                continue
            if cancelled and stage_id == cancelled.id and not (
                    task.fm_cancel_reason or vals.get("fm_cancel_reason")):
                raise UserError(_(
                    "\"%s\": use the Cancel Visit button — a cancellation "
                    "reason is required.", task.display_name))
            if completed and stage_id == completed.id and not (
                    task.fm_visit_completed_at or vals.get("fm_visit_completed_at")):
                raise UserError(_(
                    "\"%s\": use the Complete Visit button — it stamps the "
                    "check-out, records the field report and raises any "
                    "follow-up automatically.", task.display_name))
            if in_progress and stage_id == in_progress.id and not (
                    task.fm_visit_started_at or vals.get("fm_visit_started_at")):
                raise UserError(_(
                    "\"%s\": use the Start Visit button — it checks the "
                    "technician in.", task.display_name))

    # ------------------------------------------------------------------
    # Daily watchdog
    # ------------------------------------------------------------------
    @api.model
    def _cron_fm_visit_escalations(self):
        """Raise an activity on a visit that is past its plan and not started.

        Safe to run unattended, unlike the visit generator: it creates an
        activity for a person to look at and writes no visits into anybody's
        calendar.

        "Overdue" here means a full day past the planned start with no
        check-in. That is provable from the record. A true SLA deadline
        would have to come from the contract's SLA rules and the visit's
        severity, which is not wired to the visit yet — so it is not
        claimed. Where a database carries its own SLA due field, it is used
        as well.

        ``fm_sla_escalated`` makes it once per visit: a watchdog that chases
        the same job every morning is one everybody learns to filter out.
        """
        now = fields.Datetime.now()
        base = [
            ("project_id.is_fsm", "=", True),
            ("stage_id.fold", "=", False),
            ("fm_sla_escalated", "=", False),
        ]
        overdue = self.search(base + [
            ("fm_visit_started_at", "=", False),
            ("planned_date_begin", "<", now - timedelta(days=1)),
        ])
        if "x_sla_due" in self._fields:
            overdue |= self.search(base + [("x_sla_due", "<", now)])
        for task in overdue:
            if not task._fm_is_guarded_visit():
                continue
            assignee = task.user_ids[:1] or task.project_id.user_id
            task.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Visit overdue — not started"),
                note=_("This visit is more than a day past its planned start "
                       "and has not been checked in. Reschedule it, or get a "
                       "technician on site."),
                user_id=assignee.id if assignee else self.env.user.id,
            )
            task.fm_sla_escalated = True


    @api.depends("planned_date_begin")
    def _compute_fm_time_slot(self):
        """Tag every job with exactly one slot, read off its planned start.

        Derived rather than stored independently so the tag cannot go stale:
        a dispatcher who drags a job from the morning to the night slot on
        the planning Gantt gets the tag moved with it, and a job created by
        hand is tagged without anyone remembering to.

        The hour is read straight off ``planned_date_begin``, which is the
        same value the generator writes from the contract's start time. Note
        that field is a UTC Datetime while the generator treats the contract
        time as a wall clock, so both sides share one interpretation -- see
        CLAUDE.md section 4; correcting that is a separate change, because it
        would move every already-planned visit.
        """
        for task in self:
            if task.planned_date_begin:
                begin = task.planned_date_begin
                task.fm_time_slot = slot_for_hour(begin.hour + begin.minute / 60.0)
            else:
                task.fm_time_slot = False


class ProjectTaskType(models.Model):
    """Which stages may not be entered without a service document.

    A flag on the stage rather than a hardcoded stage id: the business can
    mark another stage as document-requiring from the UI, and the guard in
    project.task stays honest about *why* it is refusing.
    """

    _inherit = "project.task.type"

    fm_requires_document = fields.Boolean(
        string="Requires Service Document",
        help="A visit cannot enter this stage until a photo or signed "
             "service report is attached. The client's process document "
             "requires this to be enforced in system logic, not left "
             "optional for any user role.",
    )
