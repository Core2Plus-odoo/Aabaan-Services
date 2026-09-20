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

    Hangs off the contract, which is the sale order. ``order_id`` is not
    required at column level: it shared that column with a ``contract_id``
    onto the retired ``fm.contract`` until that model was dropped, and a
    rule created from the order's list gets it filled in by the One2many
    anyway.
    """

    _name = "fm.sla.rule"
    _description = "FM SLA Rule"
    _order = "severity"

    order_id = fields.Many2one(
        "sale.order", string="Contract", ondelete="cascade", index=True
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

    @api.depends("order_id.currency_id")
    def _compute_currency_id(self):
        for rule in self:
            parent = rule.order_id
            rule.currency_id = parent.currency_id
