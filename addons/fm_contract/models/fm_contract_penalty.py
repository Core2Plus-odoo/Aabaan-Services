# -*- coding: utf-8 -*-
from odoo import fields, models


class FmContractPenalty(models.Model):
    """Penalty / credit clauses attached to a contract (brief §5.5)."""

    _name = "fm.contract.penalty"
    _description = "FM Contract Penalty Clause"

    contract_id = fields.Many2one("fm.contract", required=True, ondelete="cascade", index=True)
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
    currency_id = fields.Many2one(related="contract_id.currency_id")
    notes = fields.Text()
