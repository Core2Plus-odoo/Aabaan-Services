# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmContractPenalty(models.Model):
    """Penalty / credit clauses attached to a contract (brief §5.5).

    Hangs off the contract, which is the sale order; see fm.sla.rule for
    why ``order_id`` is not required at column level.
    """

    _name = "fm.contract.penalty"
    _description = "FM Contract Penalty Clause"

    order_id = fields.Many2one(
        "sale.order", string="Contract", ondelete="cascade", index=True
    )
    name = fields.Char(required=True)
    trigger = fields.Selection(
        [
            ("sla_breach", "SLA Breach"),
            ("availability", "Availability Shortfall"),
            ("compliance", "Compliance Lapse"),
            ("other", "Other"),
        ],
        default="sla_breach",
        required=True,
    )
    amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency", compute="_compute_currency_id", store=True
    )

    @api.depends("order_id.currency_id")
    def _compute_currency_id(self):
        for penalty in self:
            parent = penalty.order_id
            penalty.currency_id = parent.currency_id
    notes = fields.Text()
