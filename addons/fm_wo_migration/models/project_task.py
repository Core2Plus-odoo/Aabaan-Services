# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    legacy_workorder_id = fields.Integer(
        string="Legacy Work Order ID",
        index=True,
        copy=False,
        help="Source fm.workorder row this task was converted from (re-base migration).",
    )
