# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES


class FmContractAgreementTemplate(models.Model):
    """Editable per-service wording for the printed Quotation and Service
    Agreement (fm_documents reports).

    The parts of those documents that genuinely differ by service line — the
    service description, the scope-of-work methodology, the schedule clause,
    and the default exclusions — live here instead of being hard-coded in the
    QWeb report, so an account manager can maintain a "Pest Control", a
    "Cleaning", an "HVAC AMC" wording set, etc. without touching code. A
    contract picks one via ``agreement_template_id``; the reports fall back to
    generic wording when no template is set or a field is left blank.
    """

    _name = "fm.contract.agreement.template"
    _description = "FM Contract/Quotation Agreement Template"
    _order = "service_line, name"

    name = fields.Char(required=True, translate=True)
    service_line = fields.Selection(SERVICE_LINES, required=True, index=True)
    active = fields.Boolean(default=True)

    quotation_intro_text = fields.Text(
        translate=True,
        string="Quotation Intro",
        help="Greeting/intro paragraph on the Quotation, after 'Dear ...'.",
    )
    scope_method_text = fields.Text(
        translate=True,
        string="Scope of Work (methodology)",
        help="Quotation's 'Scope of Work' paragraph — the general methodology, "
        "not the site-specific area list (that stays on the contract's own "
        "Scope of Work / Covered Area field).",
    )
    service_text = fields.Text(
        translate=True,
        string="Service Agreement — Article 2 (Service)",
    )
    schedule_text = fields.Text(
        translate=True,
        string="Service Agreement — Article 4 (Service Schedule)",
    )
    exclusions_default_text = fields.Text(
        translate=True,
        string="Default Exclusions",
        help="Used for Article 6 / the Quotation when the contract itself has "
        "no Exclusions listed.",
    )
