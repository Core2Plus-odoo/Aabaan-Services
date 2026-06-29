# -*- coding: utf-8 -*-
from odoo import fields, models


def _default_aed(env):
    """AED if present in the database, else the company currency."""
    return env.ref("base.AED", raise_if_not_found=False)


class ResCompany(models.Model):
    """Branding configuration is stored per company so each C2P-hosted tenant
    can have its own logo, palette and signature block while the codebase stays
    identical (brief §2.3, §5.1). res.config.settings exposes these fields.
    """

    _inherit = "res.company"

    fm_brand_name = fields.Char(string="FM Brand Name", default="FM Platform")
    fm_brand_logo = fields.Binary(string="FM Brand Logo")
    fm_brand_color_primary = fields.Char(string="FM Primary Color", default="#1F4434")
    fm_brand_color_accent = fields.Char(string="FM Accent Color", default="#B8923A")
    fm_default_currency_id = fields.Many2one(
        "res.currency",
        string="FM Default Currency",
        default=lambda self: _default_aed(self.env),
    )
    fm_default_vat_rate = fields.Float(string="FM Default VAT %", default=5.0)
    fm_compliance_country = fields.Selection(
        [
            ("ae", "United Arab Emirates"),
            ("om", "Oman"),
            ("sa", "Saudi Arabia"),
            ("bh", "Bahrain"),
            ("qa", "Qatar"),
            ("kw", "Kuwait"),
        ],
        string="FM Compliance Country",
        default="ae",
    )
