# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmServiceMaterial(models.Model):
    """A material/consumable used by a service, per visit (a service BoM line)."""

    _name = "fm.service.material"
    _description = "FM Service Material (per-visit composition)"
    _order = "service_tmpl_id, sequence, id"

    sequence = fields.Integer(default=10)
    service_tmpl_id = fields.Many2one(
        "product.template",
        string="Service",
        required=True,
        ondelete="cascade",
        index=True,
        domain=[("type", "=", "service")],
        help="The service product this material is consumed by.",
    )
    material_id = fields.Many2one(
        "product.product",
        string="Material / Product",
        required=True,
        index=True,
        help="The consumable/material used.",
    )
    qty_per_visit = fields.Float(
        string="Qty per Visit", default=1.0, digits="Product Unit of Measure"
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        compute="_compute_uom_id",
        store=True,
        readonly=False,
    )
    billable = fields.Boolean(
        string="Billable to Customer",
        default=False,
        help="Whether this material is charged to the customer (vs. included in the service).",
    )
    unit_cost = fields.Float(
        string="Unit Cost", related="material_id.standard_price", readonly=True
    )
    currency_id = fields.Many2one(related="material_id.currency_id", readonly=True)
    est_cost_per_visit = fields.Monetary(
        string="Est. Cost / Visit",
        compute="_compute_est_cost",
        store=True,
        currency_field="currency_id",
    )
    notes = fields.Char(string="Notes / Dilution / Brand")
    company_id = fields.Many2one(
        "res.company", related="service_tmpl_id.company_id", store=True
    )

    @api.depends("material_id")
    def _compute_uom_id(self):
        for line in self:
            if line.material_id and not line.uom_id:
                line.uom_id = line.material_id.uom_id

    @api.depends("qty_per_visit", "unit_cost")
    def _compute_est_cost(self):
        for line in self:
            line.est_cost_per_visit = (line.qty_per_visit or 0.0) * (line.unit_cost or 0.0)

    _uniq = models.Constraint(
        "unique(service_tmpl_id, material_id)",
        "This material is already listed for that service.",
    )
