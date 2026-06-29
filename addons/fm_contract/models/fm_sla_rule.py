# -*- coding: utf-8 -*-
from odoo import fields, models

SEVERITY = [
    ("p1_critical", "P1 — Critical"),
    ("p2_high", "P2 — High"),
    ("p3_medium", "P3 — Medium"),
    ("p4_low", "P4 — Low"),
]


class FmSlaRule(models.Model):
    """Per-contract SLA targets by severity (brief §5.5). Breach detection
    against live work orders is implemented in fm_sla / fm_workorder.
    """

    _name = "fm.sla.rule"
    _description = "FM SLA Rule"
    _order = "severity"

    contract_id = fields.Many2one("fm.contract", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    severity = fields.Selection(SEVERITY, required=True, default="p3_medium")
    response_target_minutes = fields.Integer(string="Response Target (min)", required=True)
    resolution_target_minutes = fields.Integer(string="Resolution Target (min)", required=True)
    business_hours_only = fields.Boolean(default=False)
    penalty_per_breach = fields.Monetary(currency_field="currency_id")
    credit_per_breach = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="contract_id.currency_id")
