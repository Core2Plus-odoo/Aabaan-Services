# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.fm_contract.models.fm_sla_rule import SEVERITY

# Allowed stage transitions (brief §6.1). Keyed by current stage.
STAGE_TRANSITIONS = {
    "draft": ["assigned", "cancelled"],
    "assigned": ["acknowledged", "cancelled"],
    "acknowledged": ["arrived", "cancelled"],
    "arrived": ["in_progress", "cancelled"],
    "in_progress": ["awaiting_parts", "awaiting_customer", "completed", "cancelled"],
    "awaiting_parts": ["in_progress", "cancelled"],
    "awaiting_customer": ["in_progress", "cancelled"],
    "completed": ["signed_off", "in_progress", "cancelled"],
    "signed_off": [],
    "cancelled": [],
}


class FmWorkOrder(models.Model):
    """Facility Management work order (brief §5.3). Composes with
    maintenance.request and implements the FM state machine via a single
    guarded ``action_stage_change`` method (brief §6.1).
    """

    _name = "fm.workorder"
    _inherit = ["maintenance.request", "mail.thread", "mail.activity.mixin"]
    _description = "FM Work Order"
    _order = "priority desc, create_date desc"

    # Identity
    name = fields.Char(default="/", copy=False, readonly=True, tracking=True)
    wo_type = fields.Selection(
        [
            ("reactive", "Reactive"),
            ("ppm", "PPM / Planned"),
            ("compliance", "Compliance"),
            ("project", "Project"),
            ("inspection", "Inspection"),
        ],
        required=True,
        default="reactive",
        tracking=True,
    )
    severity = fields.Selection(SEVERITY, required=True, default="p3_medium", tracking=True)

    stage = fields.Selection(
        [
            ("draft", "Draft"),
            ("assigned", "Assigned"),
            ("acknowledged", "Acknowledged"),
            ("arrived", "Arrived On Site"),
            ("in_progress", "In Progress"),
            ("awaiting_parts", "Awaiting Parts"),
            ("awaiting_customer", "Awaiting Customer"),
            ("completed", "Completed"),
            ("signed_off", "Signed Off"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        group_expand="_group_expand_stage",
    )

    # Relationships
    asset_id = fields.Many2one("fm.asset", string="Asset", required=True, tracking=True, index=True)
    service_line = fields.Selection(related="asset_id.service_line", store=True, index=True)
    location_id = fields.Many2one(related="asset_id.location_fm_id", store=True, string="Location")
    customer_id = fields.Many2one("res.partner", string="Customer", required=True, tracking=True, index=True)
    contract_id = fields.Many2one("fm.contract", string="Contract", tracking=True, index=True)
    technician_id = fields.Many2one("hr.employee", string="Technician", tracking=True, index=True)
    reporter_id = fields.Many2one("res.partner", string="Reported By")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)

    # Problem & resolution
    problem_description = fields.Text(required=True, tracking=True)
    resolution_notes = fields.Text(tracking=True)
    root_cause = fields.Char()

    # Scheduling
    schedule_date_start = fields.Datetime(tracking=True, index=True)
    schedule_date_end = fields.Datetime(tracking=True)
    actual_start = fields.Datetime(readonly=True)
    actual_end = fields.Datetime(readonly=True)
    acknowledged_at = fields.Datetime(readonly=True)
    duration_minutes = fields.Float(compute="_compute_duration", store=True)

    # SLA (targets here; actuals/breach computed in fm_sla)
    sla_id = fields.Many2one("fm.sla.rule", compute="_compute_sla", store=True)
    sla_response_target_min = fields.Integer(related="sla_id.response_target_minutes", store=True)
    sla_resolution_target_min = fields.Integer(related="sla_id.resolution_target_minutes", store=True)
    sla_paused = fields.Boolean(default=False)
    sla_pause_minutes_total = fields.Integer(default=0)
    last_pause_start = fields.Datetime(readonly=True)

    # Checklist
    checklist_template_id = fields.Many2one("fm.checklist.template")
    checklist_item_ids = fields.One2many("fm.workorder.checklist.item", "workorder_id")
    checklist_progress_pct = fields.Float(compute="_compute_checklist_progress", store=True)
    checklist_mandatory_complete = fields.Boolean(compute="_compute_checklist_progress", store=True)

    # Parts & labor
    parts_line_ids = fields.One2many("fm.workorder.parts.line", "workorder_id")
    labor_line_ids = fields.One2many("fm.workorder.labor.line", "workorder_id")
    parts_cost_total = fields.Monetary(compute="_compute_costs", store=True, currency_field="currency_id")
    labor_hours_total = fields.Float(compute="_compute_costs", store=True)
    labor_cost_total = fields.Monetary(compute="_compute_costs", store=True, currency_field="currency_id")
    total_cost = fields.Monetary(compute="_compute_costs", store=True, currency_field="currency_id")

    # Customer sign-off
    signed_off_by = fields.Char()
    signed_off_role = fields.Char()
    signed_off_signature = fields.Image()
    signed_off_at = fields.Datetime(readonly=True)
    csat_rating = fields.Selection(
        [("1", "1 — Very Dissatisfied"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5 — Very Satisfied")]
    )
    csat_comment = fields.Text()

    # Cancellation
    cancel_reason = fields.Text()
    cancelled_by = fields.Many2one("res.users", readonly=True)
    cancelled_at = fields.Datetime(readonly=True)

    # Linked
    invoice_id = fields.Many2one("account.move", readonly=True, copy=False)

    _sql_constraints = [
        ("wo_name_uniq", "unique(name)", "The work order reference must be unique."),
    ]

    # ------------------------------------------------------------------
    @api.model
    def _group_expand_stage(self, stages, domain):
        return [s[0] for s in self._fields["stage"].selection]

    @api.depends("actual_start", "actual_end")
    def _compute_duration(self):
        for wo in self:
            if wo.actual_start and wo.actual_end and wo.actual_end > wo.actual_start:
                wo.duration_minutes = (wo.actual_end - wo.actual_start).total_seconds() / 60.0
            else:
                wo.duration_minutes = 0.0

    @api.depends("contract_id", "severity", "contract_id.sla_rule_ids.severity")
    def _compute_sla(self):
        for wo in self:
            rule = False
            if wo.contract_id:
                rule = wo.contract_id.sla_rule_ids.filtered(lambda r: r.severity == wo.severity)[:1]
            wo.sla_id = rule.id if rule else False

    @api.depends(
        "checklist_item_ids.is_done",
        "checklist_item_ids.is_mandatory",
    )
    def _compute_checklist_progress(self):
        for wo in self:
            items = wo.checklist_item_ids
            total = len(items)
            done = len(items.filtered("is_done"))
            wo.checklist_progress_pct = (done / total * 100.0) if total else 0.0
            mandatory = items.filtered("is_mandatory")
            wo.checklist_mandatory_complete = all(mandatory.mapped("is_done")) if mandatory else True

    @api.depends(
        "parts_line_ids.total",
        "labor_line_ids.cost",
        "labor_line_ids.hours",
    )
    def _compute_costs(self):
        for wo in self:
            wo.parts_cost_total = sum(wo.parts_line_ids.mapped("total"))
            wo.labor_hours_total = sum(wo.labor_line_ids.mapped("hours"))
            wo.labor_cost_total = sum(wo.labor_line_ids.mapped("cost"))
            wo.total_cost = wo.parts_cost_total + wo.labor_cost_total

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") in (False, "/"):
                vals["name"] = self.env["ir.sequence"].next_by_code("fm.workorder") or "/"
            # Seed checklist from template if provided at creation
        records = super().create(vals_list)
        for wo in records:
            if wo.checklist_template_id and not wo.checklist_item_ids:
                wo._populate_checklist_from_template()
        return records

    def _populate_checklist_from_template(self):
        self.ensure_one()
        self.checklist_item_ids = [
            (0, 0, {
                "sequence": item.sequence,
                "text": item.text,
                "is_mandatory": item.is_mandatory,
            })
            for item in self.checklist_template_id.item_ids
        ]

    def write(self, vals):
        # Repopulate checklist when the template changes
        res = super().write(vals)
        if vals.get("checklist_template_id"):
            for wo in self:
                if not wo.checklist_item_ids:
                    wo._populate_checklist_from_template()
        return res

    # ------------------------------------------------------------------
    # State machine (brief §6.1)
    # ------------------------------------------------------------------
    def action_stage_change(self, new_stage, **kwargs):
        """Single guarded entry point for all stage transitions."""
        self.ensure_one()
        allowed = STAGE_TRANSITIONS.get(self.stage, [])
        if new_stage not in allowed:
            raise UserError(
                _("Cannot move work order from '%(from)s' to '%(to)s'.")
                % {"from": self.stage, "to": new_stage}
            )

        now = fields.Datetime.now()
        vals = {"stage": new_stage}

        if new_stage == "acknowledged" and not self.acknowledged_at:
            vals["acknowledged_at"] = now
        elif new_stage == "arrived" and not self.actual_start:
            # arrival does not start work; actual_start is set at in_progress
            pass
        elif new_stage == "in_progress":
            if not self.actual_start:
                vals["actual_start"] = now
            # resuming from a pause
            if self.sla_paused:
                vals["sla_paused"] = False
                if self.last_pause_start:
                    paused = (now - self.last_pause_start).total_seconds() / 60.0
                    vals["sla_pause_minutes_total"] = self.sla_pause_minutes_total + int(paused)
                    vals["last_pause_start"] = False
        elif new_stage in ("awaiting_parts", "awaiting_customer"):
            vals["sla_paused"] = True
            vals["last_pause_start"] = now
        elif new_stage == "completed":
            if not self.checklist_mandatory_complete:
                raise UserError(_("All mandatory checklist items must be completed before marking the work order complete."))
            vals["actual_end"] = now
        elif new_stage == "signed_off":
            if not self.signed_off_signature and not kwargs.get("signature"):
                raise UserError(_("A customer signature is required to sign off the work order."))
            if not self.csat_rating and not kwargs.get("csat_rating"):
                raise UserError(_("A CSAT rating is required to sign off the work order."))
            vals["signed_off_at"] = now
            for f in ("signed_off_by", "signed_off_role", "csat_rating", "csat_comment"):
                if kwargs.get(f):
                    vals[f] = kwargs[f]
            if kwargs.get("signature"):
                vals["signed_off_signature"] = kwargs["signature"]
        elif new_stage == "cancelled":
            vals["cancelled_by"] = self.env.uid
            vals["cancelled_at"] = now
            if kwargs.get("cancel_reason"):
                vals["cancel_reason"] = kwargs["cancel_reason"]

        self.write(vals)
        self.message_post(body=_("Stage changed to %s") % dict(self._fields["stage"].selection).get(new_stage))
        return True

    # Convenience action buttons (used by the form header)
    def action_assign(self):
        return self.action_stage_change("assigned")

    def action_acknowledge(self):
        return self.action_stage_change("acknowledged")

    def action_arrive(self):
        return self.action_stage_change("arrived")

    def action_start(self):
        return self.action_stage_change("in_progress")

    def action_complete(self):
        return self.action_stage_change("completed")

    def action_signoff(self):
        # Uses signature / CSAT already captured on the record.
        return self.action_stage_change("signed_off")

    def action_cancel(self):
        # Uses cancel_reason already captured on the record.
        return self.action_stage_change("cancelled")
