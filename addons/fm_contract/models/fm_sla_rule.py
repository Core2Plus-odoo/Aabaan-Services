# -*- coding: utf-8 -*-
from odoo import api, fields, models

SEVERITY = [
    ("p1_critical", "P1 — Critical"),
    ("p2_high", "P2 — High"),
    ("p3_medium", "P3 — Medium"),
    ("p4_low", "P4 — Low"),
]


class FmSlaRule(models.Model):
    """Per-contract SLA targets by severity (brief §5.5).

    Hangs off whichever record is the contract: ``order_id`` for a contract
    written in Sales, ``contract_id`` for a legacy ``fm.contract``. Neither
    is required at column level while both exist — a rule belongs to exactly
    one of them, so requiring either would make the other impossible.
    """

    _name = "fm.sla.rule"
    _description = "FM SLA Rule"
    _order = "severity"

    order_id = fields.Many2one(
        "sale.order", string="Contract", ondelete="cascade", index=True
    )
    contract_id = fields.Many2one(
        "fm.contract", string="Contract (legacy)", ondelete="cascade", index=True
    )
    name = fields.Char(required=True)
    severity = fields.Selection(SEVERITY, required=True, default="p3_medium")
    response_target_minutes = fields.Integer(string="Response Target (min)", required=True)
    resolution_target_minutes = fields.Integer(string="Resolution Target (min)", required=True)
    business_hours_only = fields.Boolean(default=False)
    penalty_per_breach = fields.Monetary(currency_field="currency_id")
    credit_per_breach = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", compute="_compute_currency_id", store=True
    )

    @api.depends("order_id.currency_id", "contract_id.currency_id")
    def _compute_currency_id(self):
        for rule in self:
            parent = rule.order_id or rule.contract_id
            rule.currency_id = parent.currency_id
