# Copyright 2022 360 ERP (<https://www.360erp.nl>)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Local change (Aabaan): the letterhead uploaded here is printed behind
    # every PDF report of documents belonging to this company. There is no
    # per-report list to maintain.
    pdf_watermark = fields.Binary(
        "Letterhead",
        help="Upload a PDF (or an image) to use as the company letterhead. It is "
        "printed behind every PDF report of this company's documents.",
    )
