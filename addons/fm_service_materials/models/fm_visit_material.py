# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmVisitMaterial(models.Model):
    """Material expected/used on a single visit (work order).

    ``qty_expected`` is planned (loaded from the service composition) and drives
    the material forecast; ``qty_used`` is what the technician actually consumed.
    """

    _name = "fm.visit.material"
    _description = "FM Visit Material"
    _order = "task_id, id"

    task_id = fields.Many2one(
        "project.task", string="Work Order", required=True, ondelete="cascade", index=True
    )
    material_id = fields.Many2one("product.product", string="Material", required=True, index=True)
    qty_expected = fields.Float("Qty Expected", digits="Product Unit of Measure")
    qty_used = fields.Float("Qty Used", digits="Product Unit of Measure")
    uom_id = fields.Many2one("uom.uom", string="Unit")
    billable = fields.Boolean("Billable")
    notes = fields.Char()

    # Reporting dimensions (from the work order)
    date_deadline = fields.Date(related="task_id.date_deadline", store=True, string="Visit Date")
    partner_id = fields.Many2one(related="task_id.partner_id", store=True, string="Customer")
    service_line = fields.Selection(related="task_id.fm_service_line", store=True)
    contract_id = fields.Many2one(related="task_id.fm_contract_id", store=True, string="Contract")
    company_id = fields.Many2one(related="task_id.company_id", store=True)
    currency_id = fields.Many2one(related="material_id.currency_id")
    unit_cost = fields.Float(related="material_id.standard_price")
    cost_expected = fields.Monetary(compute="_compute_costs", store=True, currency_field="currency_id")
    cost_used = fields.Monetary(compute="_compute_costs", store=True, currency_field="currency_id")

    @api.depends("qty_expected", "qty_used", "unit_cost")
    def _compute_costs(self):
        for line in self:
            line.cost_expected = (line.qty_expected or 0.0) * (line.unit_cost or 0.0)
            line.cost_used = (line.qty_used or 0.0) * (line.unit_cost or 0.0)
