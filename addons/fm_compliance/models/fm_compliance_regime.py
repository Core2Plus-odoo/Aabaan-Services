# -*- coding: utf-8 -*-
from odoo import fields, models

COUNTRIES = [
    ("ae", "United Arab Emirates"),
    ("om", "Oman"),
    ("sa", "Saudi Arabia"),
    ("bh", "Bahrain"),
    ("qa", "Qatar"),
    ("kw", "Kuwait"),
]


class FmComplianceRegime(models.Model):
    """A regulatory regime (e.g. Civil Defence fire systems) (brief §5.6)."""

    _name = "fm.compliance.regime"
    _description = "FM Compliance Regime"

    name = fields.Char(required=True, translate=True)
    country = fields.Selection(COUNTRIES, default="ae")
    authority = fields.Char(help="e.g. Civil Defence, DEWA, Dubai Municipality")
    regulation_code = fields.Char()
    description = fields.Text(translate=True)
    applies_to_asset_category_ids = fields.Many2many("fm.asset.category", string="Applies To Categories")
    task_template_ids = fields.One2many("fm.compliance.task.template", "regime_id", string="Task Templates")
    active = fields.Boolean(default=True)


class FmComplianceTaskTemplate(models.Model):
    _name = "fm.compliance.task.template"
    _description = "FM Compliance Task Template"

    regime_id = fields.Many2one("fm.compliance.regime", required=True, ondelete="cascade")
    name = fields.Char(required=True, translate=True)
    frequency_unit = fields.Selection([("month", "Months"), ("year", "Years")], default="year")
    frequency_value = fields.Integer(default=1)
    certificate_required = fields.Boolean(default=True)
    lead_days = fields.Integer(string="Generate WO N days before due", default=30)
