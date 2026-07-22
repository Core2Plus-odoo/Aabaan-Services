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
    replaces_standard_articles = fields.Boolean(
        string="Defines the Full Document",
        default=True,
        help="When on (recommended), this template's Additional Terms ARE the "
        "printed Service Agreement's articles — auto-numbered after the "
        "Duration article — instead of the generic 18-article skeleton. "
        "Each real Aaban service has its own article structure (Water Tank: "
        "Tank Details/Safety/Customer Responsibility...; Anti-Termite: "
        "Treatment Type/Warranty...; Dubai Pest Control: Municipality Local "
        "Order 11 terms), which this preserves faithfully. Switch off only "
        "for a template that merely re-words the generic skeleton.",
    )

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
    line_ids = fields.One2many(
        "fm.contract.agreement.template.line", "template_id",
        string="Additional Terms",
        help="Free-form extra articles this service needs that the standard "
        "skeleton doesn't have — e.g. Tank Details, Warranty Certificate, "
        "Customer Responsibility, Materials & Methods. Printed as their own "
        "headed sections; copied onto a contract when this template is "
        "selected.",
    )


class FmContractAgreementTemplateLine(models.Model):
    """One custom article on an agreement template — a free heading + body,
    for the service-specific terms that don't fit the standard skeleton
    (e.g. water tank cleaning's 'Tank Details', anti-termite's 'Warranty
    Certificate')."""

    _name = "fm.contract.agreement.template.line"
    _description = "FM Contract Agreement Template — Additional Term"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "fm.contract.agreement.template", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Heading", required=True, translate=True)
    body = fields.Text(string="Body", required=True, translate=True)
