# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    fm_service_product_id = fields.Many2one(
        "product.template",
        string="Service",
        domain=[("type", "=", "service")],
        help="Service delivered on this visit; its composition drives the expected materials.",
    )
    fm_material_line_ids = fields.One2many(
        "fm.visit.material", "task_id", string="Materials"
    )
    fm_currency_id = fields.Many2one(related="company_id.currency_id", string="FM Currency")
    fm_material_expected_cost = fields.Monetary(
        compute="_compute_fm_material_cost", currency_field="fm_currency_id"
    )
    fm_material_used_cost = fields.Monetary(
        compute="_compute_fm_material_cost", currency_field="fm_currency_id"
    )

    @api.depends("fm_material_line_ids.cost_expected", "fm_material_line_ids.cost_used")
    def _compute_fm_material_cost(self):
        for task in self:
            task.fm_material_expected_cost = sum(task.fm_material_line_ids.mapped("cost_expected"))
            task.fm_material_used_cost = sum(task.fm_material_line_ids.mapped("cost_used"))

    @api.onchange("fm_contract_id")
    def _onchange_fm_contract_default_service(self):
        """Default the service from the contract when it has a single service product."""
        for task in self:
            if task.fm_service_product_id or not task.fm_contract_id:
                continue
            services = task.fm_contract_id.order_line.product_id.product_tmpl_id.filtered(
                lambda p: p.type == "service" and p.fm_service_material_ids
            )
            if len(services) == 1:
                task.fm_service_product_id = services

    def action_load_expected_materials(self):
        """(Re)load the expected material lines from the service composition."""
        Line = self.env["fm.visit.material"]
        for task in self:
            service = task.fm_service_product_id
            if not service:
                continue
            existing = task.fm_material_line_ids.mapped("material_id")
            for comp in service.fm_service_material_ids:
                if comp.material_id in existing:
                    continue
                Line.create({
                    "task_id": task.id,
                    "material_id": comp.material_id.id,
                    "qty_expected": comp.qty_per_visit,
                    "uom_id": comp.uom_id.id,
                    "billable": comp.billable,
                    "notes": comp.notes,
                })
        return True

    def _fm_autoload_materials(self):
        """Server-side helper: set a single-service default and load its materials.
        Used when generating visits so the forecast has data without manual clicks."""
        for task in self:
            if not task.fm_service_product_id and task.fm_contract_id:
                services = task.fm_contract_id.order_line.product_id.product_tmpl_id.filtered(
                    lambda p: p.type == "service" and p.fm_service_material_ids
                )
                if len(services) == 1:
                    task.fm_service_product_id = services
            if task.fm_service_product_id and not task.fm_material_line_ids:
                task.action_load_expected_materials()
