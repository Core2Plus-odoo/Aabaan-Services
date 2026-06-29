# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmAssetLocation(models.Model):
    """Physical location hierarchy: Site → Building → Floor → Zone → Room
    (brief §5.2). ``full_path`` gives a human breadcrumb like
    "Tower A / L34 / MPR".
    """

    _name = "fm.asset.location"
    _description = "FM Asset Location"
    _parent_store = True
    _parent_name = "parent_id"
    _order = "full_path"

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    location_type = fields.Selection(
        [
            ("site", "Site"),
            ("building", "Building"),
            ("floor", "Floor"),
            ("zone", "Zone"),
            ("room", "Room"),
        ],
        required=True,
        default="building",
    )
    parent_id = fields.Many2one("fm.asset.location", string="Parent Location", ondelete="restrict", index=True)
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many("fm.asset.location", "parent_id", string="Sub-locations")
    site_id = fields.Many2one(
        "fm.asset.location",
        string="Site",
        compute="_compute_site_id",
        store=True,
        recursive=True,
    )
    full_path = fields.Char(compute="_compute_full_path", store=True, recursive=True)
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    gross_area_sqm = fields.Float(string="Gross Area (sqm)")
    asset_count = fields.Integer(compute="_compute_asset_count")
    active = fields.Boolean(default=True)

    @api.depends("name", "parent_id.full_path")
    def _compute_full_path(self):
        for loc in self:
            if loc.parent_id:
                loc.full_path = "%s / %s" % (loc.parent_id.full_path, loc.name)
            else:
                loc.full_path = loc.name

    @api.depends("location_type", "parent_id.site_id")
    def _compute_site_id(self):
        for loc in self:
            if loc.location_type == "site":
                loc.site_id = loc
            elif loc.parent_id:
                loc.site_id = loc.parent_id.site_id
            else:
                loc.site_id = False

    def _compute_asset_count(self):
        groups = self.env["fm.asset"]._read_group(
            [("location_fm_id", "in", self.ids)], ["location_fm_id"], ["__count"]
        )
        counts = {loc.id: count for loc, count in groups}
        for loc in self:
            loc.asset_count = counts.get(loc.id, 0)

    @api.depends("full_path")
    def _compute_display_name(self):
        for loc in self:
            loc.display_name = loc.full_path or loc.name
