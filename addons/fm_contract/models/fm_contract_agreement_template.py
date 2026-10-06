# -*- coding: utf-8 -*-
import re

from markupsafe import Markup, escape

from odoo import fields, models

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES


# What a line of an agreement is on a Client Document Layout:
# an article (heading + body), the parties' block (no heading printed),
# or the place the priced lines are printed.
LINE_KINDS = [
    ("article", "Article"),
    ("parties", "Parties Block"),
    ("price_table", "Price Table"),
]


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
    # Aaban's own contract documents, printed the way the client writes them:
    # the template's lines ARE the document body, in order, each printed
    # with its own heading ("Article 1- Duration of the contract :") rather
    # than renumbered, the parties' block and the priced table where the
    # client's document has them, and the signature block at the end.
    client_layout = fields.Boolean(
        string="Client Document Layout",
        help="Print the Service Agreement exactly in this template's own "
        "layout: its lines in order with their own headings, the price "
        "table where a Price Table line sits, and the signature block.",
    )
    signature_party = fields.Char(
        string="Signs as (First Party)",
        help="Aaban's name above its signature line, e.g. "
        "\"Aaban Classic Building Cleaning Fujairah Branch 1\".",
    )
    table_columns = fields.Char(
        string="Price Table Columns",
        default="unit,rate,frequency,tax,grand_total",
        help="After Description, comma-separated: unit, rate, frequency, "
        "tax, subtotal, grand_total.",
    )
    italic_labels = fields.Boolean(
        string="Italic Labels", default=True,
        help="Print 'Contact Person' and the 'Total Amount' line in italics, "
        "as the client's older documents do; off for the newer ones.",
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


    # ------------------------------------------------------------------
    # Print preview of the template itself
    # ------------------------------------------------------------------
    def _fm_preview_html(self, value):
        """The formatted wording with each placeholder shown as a marker
        naming it, since a template has no contract to fill it from."""
        if not value:
            return Markup("")
        chip = ('<span style="background:#FFF2C2;border:1px dashed #D2551E;color:#8A3708;'
                'font-weight:bold;padding:1px 6px;border-radius:3px;">\u270e %s</span>')
        return Markup(re.sub(r"\{\{\s*([A-Z_]+)\s*\}\}",
                             lambda m: chip % escape(m.group(1)), str(value)))

    def _fm_preview_columns(self):
        self.ensure_one()
        cols = [c.strip() for c in (self.table_columns or "").split(",")]
        return [c for c in cols if c in ("unit", "rate", "frequency", "tax", "subtotal", "grand_total")]


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
    kind = fields.Selection(LINE_KINDS, default="article", required=True)
    name = fields.Char(string="Heading", required=True, translate=True)
    body = fields.Text(string="Body", required=True, translate=True)
    body_html = fields.Html(
        string="Body (formatted)", translate=True,
        help="The body with its bold and underline, as the client writes it. "
        "Printed instead of Body on a Client Document Layout template.",
    )
