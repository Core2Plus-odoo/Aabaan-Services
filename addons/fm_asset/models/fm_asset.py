# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .fm_asset_category import CRITICALITY


class FmAsset(models.Model):
    """FM asset. Composes with the standard Maintenance app (brief §2.2 step 3):
    ``_name='fm.asset'`` + ``_inherit='maintenance.equipment'`` gives a distinct
    model — referenced everywhere as ``fm.asset`` — that reuses the equipment
    fields/behaviour while carrying FM-specific structure.

    Fields that depend on later modules (contract_id → fm_contract,
    last/next PPM → fm_ppm, MTBF → fm_workorder history, depreciation) are added
    when those modules land, per the standard-first hierarchy.
    """

    _name = "fm.asset"
    _inherit = ["maintenance.equipment", "mail.thread", "mail.activity.mixin"]
    _description = "FM Asset"

    asset_code = fields.Char(required=True, copy=False, default="/", readonly=True, index=True)
    category_fm_id = fields.Many2one("fm.asset.category", string="FM Category", required=True, index=True)
    service_line = fields.Selection(related="category_fm_id.service_line", store=True, index=True)
    location_fm_id = fields.Many2one("fm.asset.location", string="FM Location", required=True, index=True)
    location_full_path = fields.Char(related="location_fm_id.full_path", store=True, string="Location Path")
    criticality = fields.Selection(CRITICALITY, default="medium", required=True, index=True, tracking=True)
    state = fields.Selection(
        [
            ("operational", "Operational"),
            ("under_repair", "Under Repair"),
            ("standby", "Standby"),
            ("decommissioned", "Decommissioned"),
        ],
        default="operational",
        required=True,
        tracking=True,
    )
    make = fields.Char(string="Make")
    model_name = fields.Char(string="Model")
    serial_number = fields.Char(string="Serial Number")
    install_date = fields.Date()
    warranty_expiry = fields.Date(tracking=True)
    parent_asset_id = fields.Many2one("fm.asset", string="Parent Asset", index=True)
    child_asset_ids = fields.One2many("fm.asset", "parent_asset_id", string="Sub-assets")
    manufacturer_contact_id = fields.Many2one("res.partner", string="Manufacturer Contact")
    service_provider_id = fields.Many2one("res.partner", string="Service Provider")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    acquisition_cost = fields.Monetary(currency_field="currency_id")
    qr_code_data = fields.Char(compute="_compute_qr_code_data", store=True)

    _sql_constraints = [
        ("asset_code_uniq", "unique(asset_code)", "The asset code must be unique."),
    ]

    @api.depends("asset_code")
    def _compute_qr_code_data(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for asset in self:
            if asset.asset_code and asset.asset_code != "/":
                asset.qr_code_data = "%s/fm/asset/%s" % (base, asset.asset_code)
            else:
                asset.qr_code_data = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("asset_code", "/") in (False, "/"):
                vals["asset_code"] = self.env["ir.sequence"].next_by_code("fm.asset") or "/"
        return super().create(vals_list)
