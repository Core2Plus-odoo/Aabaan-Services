# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Surfaces the per-company FM branding configuration in
    Settings → FM Platform (brief §5.1). Fields are related to res.company so
    each company/tenant keeps its own values.
    """

    _inherit = "res.config.settings"

    fm_brand_name = fields.Char(
        related="company_id.fm_brand_name", readonly=False
    )
    fm_brand_logo = fields.Binary(
        related="company_id.fm_brand_logo", readonly=False
    )
    fm_brand_color_primary = fields.Char(
        related="company_id.fm_brand_color_primary", readonly=False
    )
    fm_brand_color_accent = fields.Char(
        related="company_id.fm_brand_color_accent", readonly=False
    )
    fm_default_currency_id = fields.Many2one(
        related="company_id.fm_default_currency_id", readonly=False
    )
    fm_default_vat_rate = fields.Float(
        related="company_id.fm_default_vat_rate", readonly=False
    )
    fm_compliance_country = fields.Selection(
        related="company_id.fm_compliance_country", readonly=False
    )
