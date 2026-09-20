# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.fm_contract.models.fm_sla_rule import SEVERITY
from odoo.addons.fm_fsm.models.fm_visit_schedule_mixin import (
    TIME_SLOTS,
    slot_for_hour,
)


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

    def write(self, vals):
        """Refuse to close a visit that has no service document.

        Enforced here rather than in the view so it holds for every route
        into the stage -- kanban drag, form, mobile app, import or RPC -- and
        for every user role, which is what the client's process document
        asks for ("enforced in the system logic, not optional for any user
        role").
        """
        stage_id = vals.get("stage_id")
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
