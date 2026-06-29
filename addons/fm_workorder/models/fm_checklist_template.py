# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES


class FmChecklistTemplate(models.Model):
    """Reusable checklist applied to a work order (brief §5.4). Defined here
    because fm.workorder consumes it directly; fm_ppm reuses it.
    """

    _name = "fm.checklist.template"
    _description = "FM Checklist Template"

    name = fields.Char(required=True, translate=True)
    service_line = fields.Selection(SERVICE_LINES, default="other")
    item_ids = fields.One2many("fm.checklist.template.item", "template_id", string="Items")
    active = fields.Boolean(default=True)


class FmChecklistTemplateItem(models.Model):
    _name = "fm.checklist.template.item"
    _description = "FM Checklist Template Item"
    _order = "sequence, id"

    template_id = fields.Many2one("fm.checklist.template", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    text = fields.Char(required=True, translate=True)
    is_mandatory = fields.Boolean(default=True)
    requires_photo = fields.Boolean(default=False)
