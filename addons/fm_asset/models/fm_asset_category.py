# -*- coding: utf-8 -*-
from odoo import api, fields, models

SERVICE_LINES = [
    ("hvac", "HVAC"),
    ("electrical", "Electrical"),
    ("plumbing", "Plumbing"),
    ("cleaning", "Cleaning"),
    ("pest", "Pest Control"),
    ("security", "Security"),
    ("lift", "Lifts & Escalators"),
    ("fire", "Fire & Life Safety"),
    ("bms", "BMS / Controls"),
    ("other", "Other"),
]

CRITICALITY = [
    ("critical", "Critical"),
    ("high", "High"),
    ("medium", "Medium"),
    ("low", "Low"),
]


class FmAssetCategory(models.Model):
    """Asset category with a service-line classification (brief §5.2).

    ``default_checklist_template_id`` and ``required_skill_ids`` from the brief
    are added when fm_ppm / fm_workorder introduce those models — kept out here
    to avoid a forward dependency.
    """

    _name = "fm.asset.category"
    _description = "FM Asset Category"
    _parent_store = True
    _parent_name = "parent_id"
    _order = "complete_name"

    name = fields.Char(required=True, translate=True)
    parent_id = fields.Many2one("fm.asset.category", string="Parent Category", ondelete="restrict", index=True)
    parent_path = fields.Char(index=True, unaccent=False)
    complete_name = fields.Char(compute="_compute_complete_name", store=True, recursive=True)
    child_ids = fields.One2many("fm.asset.category", "parent_id", string="Sub-categories")
    service_line = fields.Selection(SERVICE_LINES, required=True, default="other")
    default_criticality = fields.Selection(CRITICALITY, default="medium")
    default_ppm_frequency_months = fields.Integer(string="Default PPM Frequency (months)", default=3)
    asset_count = fields.Integer(compute="_compute_asset_count")
    active = fields.Boolean(default=True)

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for cat in self:
            if cat.parent_id:
                cat.complete_name = "%s / %s" % (cat.parent_id.complete_name, cat.name)
            else:
                cat.complete_name = cat.name

    def _compute_asset_count(self):
        groups = self.env["fm.asset"]._read_group(
            [("category_fm_id", "in", self.ids)], ["category_fm_id"], ["__count"]
        )
        counts = {cat.id: count for cat, count in groups}
        for cat in self:
            cat.asset_count = counts.get(cat.id, 0)
