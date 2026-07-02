# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    fm_service_material_ids = fields.One2many(
        "fm.service.material", "service_tmpl_id", string="Materials per Visit"
    )
    fm_service_material_count = fields.Integer(compute="_compute_fm_service_material_count")

    def _compute_fm_service_material_count(self):
        groups = self.env["fm.service.material"]._read_group(
            [("service_tmpl_id", "in", self.ids)], ["service_tmpl_id"], ["__count"]
        )
        counts = {t.id: n for t, n in groups}
        for tmpl in self:
            tmpl.fm_service_material_count = counts.get(tmpl.id, 0)
