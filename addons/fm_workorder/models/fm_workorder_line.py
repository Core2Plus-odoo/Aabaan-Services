# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmWorkOrderChecklistItem(models.Model):
    _name = "fm.workorder.checklist.item"
    _description = "FM Work Order Checklist Item"
    _order = "sequence, id"

    workorder_id = fields.Many2one("fm.workorder", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    text = fields.Char(required=True, translate=True)
    is_mandatory = fields.Boolean(default=True)
    is_done = fields.Boolean(default=False, tracking=True)
    done_by = fields.Many2one("res.users", readonly=True)
    done_at = fields.Datetime(readonly=True)
    photo = fields.Image()
    notes = fields.Char()

    def write(self, vals):
        if "is_done" in vals:
            if vals["is_done"]:
                vals.setdefault("done_by", self.env.uid)
                vals.setdefault("done_at", fields.Datetime.now())
            else:
                vals["done_by"] = False
                vals["done_at"] = False
        return super().write(vals)


class FmWorkOrderPartsLine(models.Model):
    _name = "fm.workorder.parts.line"
    _description = "FM Work Order Parts Line"

    workorder_id = fields.Many2one("fm.workorder", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one(
        "product.product", required=True, domain="[('type', 'in', ['consu', 'product'])]"
    )
    description = fields.Char()
    qty = fields.Float(required=True, default=1.0)
    unit_cost = fields.Monetary(currency_field="currency_id")
    total = fields.Monetary(compute="_compute_total", store=True, currency_field="currency_id")
    stock_move_id = fields.Many2one("stock.move", readonly=True)
    currency_id = fields.Many2one(related="workorder_id.currency_id")

    @api.depends("qty", "unit_cost")
    def _compute_total(self):
        for line in self:
            line.total = line.qty * line.unit_cost

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.display_name
                line.unit_cost = line.product_id.standard_price


class FmWorkOrderLaborLine(models.Model):
    _name = "fm.workorder.labor.line"
    _description = "FM Work Order Labor Line"

    workorder_id = fields.Many2one("fm.workorder", required=True, ondelete="cascade", index=True)
    technician_id = fields.Many2one("hr.employee", required=True)
    date = fields.Date(default=fields.Date.context_today)
    start_time = fields.Datetime()
    end_time = fields.Datetime()
    hours = fields.Float(compute="_compute_hours", store=True, readonly=False)
    hourly_rate = fields.Monetary(currency_field="currency_id")
    cost = fields.Monetary(compute="_compute_cost", store=True, currency_field="currency_id")
    description = fields.Char()
    analytic_account_id = fields.Many2one("account.analytic.account")
    currency_id = fields.Many2one(related="workorder_id.currency_id")

    @api.depends("start_time", "end_time")
    def _compute_hours(self):
        for line in self:
            if line.start_time and line.end_time and line.end_time > line.start_time:
                line.hours = (line.end_time - line.start_time).total_seconds() / 3600.0

    @api.depends("hours", "hourly_rate")
    def _compute_cost(self):
        for line in self:
            line.cost = line.hours * line.hourly_rate
