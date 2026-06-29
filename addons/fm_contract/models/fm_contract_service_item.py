# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES


class FmContractServiceItem(models.Model):
    """Catalog of service items used as contract inclusions/exclusions
    (brief §5.5).
    """

    _name = "fm.contract.service.item"
    _description = "FM Contract Service Item"
    _order = "service_line, name"

    name = fields.Char(required=True, translate=True)
    service_line = fields.Selection(SERVICE_LINES, default="other")
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
