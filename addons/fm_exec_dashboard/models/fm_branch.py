# -*- coding: utf-8 -*-
from odoo import fields, models


class FmBranch(models.Model):
    """Revenue target, so the dashboard can show Target and Achv %.

    Monthly rather than annual: the dashboard pro-rates it across whatever
    date range the user picks, and an annual figure cannot survive that.

    Left at zero, the dashboard shows no target rather than inferring one
    from history — a target is a management decision, and a dashboard that
    invents one is worse than a dashboard that admits it has none.
    """

    _inherit = "fm.branch"

    monthly_revenue_target = fields.Monetary(
        string="Monthly Revenue Target",
        currency_field="currency_id",
        help="Target revenue for this branch in a calendar month, excluding "
             "tax. The executive dashboard pro-rates it by the number of days "
             "in the selected period. Zero means no target is set.",
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True)
