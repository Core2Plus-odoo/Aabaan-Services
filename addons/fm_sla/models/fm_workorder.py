# -*- coding: utf-8 -*-
from odoo import api, fields, models

SLA_STATUS = [
    ("not_started", "Not Started"),
    ("on_track", "On Track"),
    ("at_risk", "At Risk"),
    ("breached", "Breached"),
    ("met", "Met"),
]

AT_RISK_THRESHOLD = 0.8  # 80% of target consumed → at risk


class FmWorkOrder(models.Model):
    """Adds SLA actuals/breach status (brief §6.2) and WO→invoice on sign-off
    (brief §6.4). The static targets/pause accounting live in fm_workorder.
    """

    _inherit = "fm.workorder"

    sla_response_actual_min = fields.Integer(compute="_compute_sla_actuals", store=True)
    sla_resolution_actual_min = fields.Integer(compute="_compute_sla_actuals", store=True)
    sla_response_status = fields.Selection(SLA_STATUS, compute="_compute_sla_status", store=True, default="not_started")
    sla_resolution_status = fields.Selection(SLA_STATUS, compute="_compute_sla_status", store=True, default="not_started")

    @api.depends("acknowledged_at", "create_date", "signed_off_at", "sla_pause_minutes_total")
    def _compute_sla_actuals(self):
        for wo in self:
            if wo.acknowledged_at and wo.create_date:
                wo.sla_response_actual_min = int((wo.acknowledged_at - wo.create_date).total_seconds() / 60)
            else:
                wo.sla_response_actual_min = 0
            if wo.signed_off_at and wo.create_date:
                elapsed = (wo.signed_off_at - wo.create_date).total_seconds() / 60
                wo.sla_resolution_actual_min = max(0, int(elapsed - (wo.sla_pause_minutes_total or 0)))
            else:
                wo.sla_resolution_actual_min = 0

    @api.depends(
        "sla_response_target_min", "sla_resolution_target_min",
        "sla_response_actual_min", "sla_resolution_actual_min",
        "acknowledged_at", "signed_off_at", "stage",
    )
    def _compute_sla_status(self):
        for wo in self:
            wo.sla_response_status = wo._status_for(
                target=wo.sla_response_target_min,
                done=bool(wo.acknowledged_at),
                actual=wo.sla_response_actual_min,
                running_anchor=wo.create_date,
            )
            wo.sla_resolution_status = wo._status_for(
                target=wo.sla_resolution_target_min,
                done=bool(wo.signed_off_at),
                actual=wo.sla_resolution_actual_min,
                running_anchor=wo.create_date,
                pause_minutes=wo.sla_pause_minutes_total or 0,
                terminal=wo.stage in ("cancelled",),
            )

    def _status_for(self, target, done, actual, running_anchor, pause_minutes=0, terminal=False):
        """Return an SLA status code for one clock."""
        if not target or terminal:
            return "not_started"
        if done:
            return "met" if actual <= target else "breached"
        if not running_anchor:
            return "not_started"
        now = fields.Datetime.now()
        elapsed = (now - running_anchor).total_seconds() / 60 - pause_minutes
        if elapsed >= target:
            return "breached"
        if elapsed >= target * AT_RISK_THRESHOLD:
            return "at_risk"
        return "on_track"

    @api.model
    def _cron_refresh_sla(self):
        """Re-evaluate in-flight SLA clocks (brief §6.2). The status computes
        depend on now(), so we force a recompute on open work orders."""
        open_wos = self.search([("stage", "not in", ("signed_off", "cancelled"))])
        open_wos._compute_sla_status()

    # ------------------------------------------------------------------
    # WO → invoice on sign-off (brief §6.4)
    # ------------------------------------------------------------------
    def action_stage_change(self, new_stage, **kwargs):
        res = super().action_stage_change(new_stage, **kwargs)
        if new_stage == "signed_off":
            for wo in self:
                wo._on_signed_off()
        return res

    def _on_signed_off(self):
        self.ensure_one()
        # Refresh contract health immediately
        if self.contract_id:
            self.contract_id._compute_fm_health()
        # Billing: only break-fix generates a per-WO invoice
        if self.contract_id and self.contract_id.contract_type == "break_fix" and not self.invoice_id:
            self._create_wo_invoice()

    def _create_wo_invoice(self):
        self.ensure_one()
        lines = []
        for p in self.parts_line_ids:
            lines.append((0, 0, {
                "name": p.description or (p.product_id.display_name if p.product_id else "Part"),
                "quantity": p.qty,
                "price_unit": p.unit_cost,
                "product_id": p.product_id.id if p.product_id else False,
            }))
        for l in self.labor_line_ids:
            if l.hours:
                lines.append((0, 0, {
                    "name": l.description or "Labor",
                    "quantity": l.hours,
                    "price_unit": l.hourly_rate,
                }))
        if not lines:
            return False
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.customer_id.id,
            "invoice_origin": self.name,
            "invoice_line_ids": lines,
        })
        self.invoice_id = move.id
        self.message_post(body="Draft invoice %s created." % move.name)
        return move
