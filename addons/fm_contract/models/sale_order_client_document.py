# -*- coding: utf-8 -*-
import re

from markupsafe import Markup, escape

from odoo import fields, models

try:
    from num2words import num2words
except ImportError:  # pragma: no cover - num2words ships with Odoo
    num2words = None

from .fm_agreement_mixin import PLACEHOLDER_RE
from .sale_order import DURATION_UNITS

# Price-table columns a Client Document Layout template may ask for.
CLIENT_TABLE_COLUMNS = ("unit", "rate", "frequency", "tax", "subtotal", "grand_total")

PENCIL = ('<span style="background:#FFF2C2;border:1px dashed #D2551E;color:#8A3708;'
          'font-weight:bold;padding:1px 7px;border-radius:3px;">✎ %s</span>')


class SaleOrder(models.Model):
    """The values Aaban's own contract document prints.

    A Client Document Layout template (see fm.contract.agreement.template)
    prints the agreement the way the client writes it; these are the facts
    of the order that document needs, in the client's own formats.
    """

    _inherit = "sale.order"

    agreement_client_layout = fields.Boolean(
        related="agreement_template_id.client_layout", string="Client Document Layout")
    agreement_signature_party = fields.Char(
        related="agreement_template_id.signature_party", string="Signs as (First Party)")
    agreement_table_columns = fields.Char(
        related="agreement_template_id.table_columns", string="Price Table Columns")
    agreement_italic_labels = fields.Boolean(
        related="agreement_template_id.italic_labels", string="Italic Labels")
    fm_client_title = fields.Char(
        string="Customer Title (printed)",
        help="Printed before the customer's name at the top of the client "
             "contract, e.g. MS.")

    @staticmethod
    def _fm_client_date(value):
        """02-Oct-2026: the client's own format, and a month in letters
        cannot be read two ways."""
        return value.strftime("%d-%b-%Y") if value else ""

    def _fm_client_reference(self):
        """Ref# as the client prints it: the order number and the year
        (1392/26), unless the order carries its own reference."""
        self.ensure_one()
        if self.client_order_ref:
            return self.client_order_ref
        number = re.sub(r"\D", "", self.name or "").lstrip("0") or "0"
        moment = self.date_order or fields.Datetime.now()
        return "%s/%s" % (number, moment.strftime("%y"))

    def _fm_client_contact(self):
        """The customer's person to deal with: the first contract contact,
        the order's contact when it is a person under the customer, or the
        customer's first contact."""
        self.ensure_one()
        if self.fm_customer_contact_ids:
            return self.fm_customer_contact_ids[:1]
        partner = self.partner_id
        if partner.parent_id:
            return partner
        return partner.child_ids.filtered(lambda p: p.type == "contact" and p.active)[:1]

    def _fm_client_payment_terms(self):
        self.ensure_one()
        return (self.payment_terms_note or "").strip() or self.payment_term_id.name or ""

    def _fm_client_values(self):
        """Placeholder values for the client document: the contract's own
        values, with the dates in the client's format and the customer's
        phone and address, which only this document prints."""
        self.ensure_one()
        values = dict(self._fm_agreement_placeholder_values())
        customer = self.partner_id.commercial_partner_id
        values.update({
            "CLIENT": customer.name or "",
            "CLIENT_PHONE": customer.phone or "",
            "CLIENT_ADDRESS": (
                customer._display_address(without_company=True).replace("\n", ", ").strip(", ")
                if customer else ""),
            "START": self._fm_client_date(self.fm_start_date),
            "END": self._fm_client_date(self.fm_end_date),
            "DATE": self._fm_client_date(self.date_order),
            "PAYMENT_TERMS": self._fm_client_payment_terms(),
            "CLIENT_TITLE": self.fm_client_title or "",
            "CLIENT_SITE": " ".join(self._fm_client_address_lines()),
            "CLIENT_ADDRESS_LINES": self._fm_client_address_lines(),
            "CONTACT_PHONE": self._fm_client_contact().phone or "",
        })
        return values

    def _fm_client_address_lines(self):
        """The customer's address as the client writes it under the Second
        Party: street, street 2, city, emirate -- one per line."""
        self.ensure_one()
        customer = self.partner_id.commercial_partner_id
        return [part for part in (customer.street, customer.street2, customer.city,
                                  customer.state_id.name) if part]

    def _fm_render_agreement_html(self, value, values=None):
        """Formatted wording with its placeholders filled in. A fact the
        order cannot supply prints as a pencil marker, never as a blank."""
        self.ensure_one()
        if not value:
            return Markup("")
        values = values if values is not None else self._fm_client_values()

        def resolve(match):
            name = match.group(1)
            found = values.get(name)
            if isinstance(found, list):
                found = Markup("<br/>").join(escape(part) for part in found)
            if found:
                return str(escape(found))
            return PENCIL % escape(name)

        return Markup(PLACEHOLDER_RE.sub(resolve, str(value)))

    def _fm_client_columns(self):
        self.ensure_one()
        cols = [c.strip() for c in (self.agreement_table_columns or "").split(",")]
        return [c for c in cols if c in CLIENT_TABLE_COLUMNS]

    def _fm_client_amount_in_words(self):
        """'Two Thousand Eight Hundred Thirty-Five Only', as the client writes it."""
        self.ensure_one()
        if num2words is None:
            return ""
        amount = self.amount_total
        integral = int(amount)
        fils = int(round((amount - integral) * 100))
        words = num2words(integral, lang="en").replace(",", "").replace(" and ", " ").title()
        if fils:
            words += " and %s Fils" % num2words(fils, lang="en").replace(" and ", " ").title()
        return words + " Only"

    @staticmethod
    def _fm_client_money(value):
        return "{:,.2f}".format(value or 0.0)

    @staticmethod
    def _fm_client_line_title(first_line):
        """A line's first description line, without the [CODE] prefix."""
        return re.sub(r"^\[[^\]]*\]\s*", "", first_line or "")


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    fm_print_unit = fields.Float(
        string="Unit (printed)",
        help="Printed in the Unit column of the client contract. A line of 1 "
        "tank cleaned twice a year is Unit 1, Frequency 'Yearly Twice', "
        "quantity 2. Left empty, the quantity is printed.",
    )
    fm_print_details = fields.Html(
        string="Details (printed)",
        help="Printed under the line's title in the client contract, "
             "formatted: the tank details, the site, the lab test. Left "
             "empty, the rest of the description is printed.",
    )
    # The line's job frequency, when the contract's Job Type is Recurring:
    # "4 / Year" is four jobs a year, one every three months; with Every
    # ticked, "Every 3 / Month" is one job every three months.
    fm_creates_job = fields.Boolean(
        string="Create Job", default=True,
        help="Whether this line becomes job(s) on the calendar. Untick it "
             "for a fee or a charge that is not a visit.")
    fm_frequency_count = fields.Integer(string="Frequency", default=1)
    fm_frequency_unit = fields.Selection(
        DURATION_UNITS, string="Frequency Unit", default="year")
    fm_frequency_every = fields.Boolean(
        string="Every",
        help="Ticked: one job every N units (Every 3 Month). "
             "Unticked: N jobs per unit (4 per Year).")
    fm_print_frequency = fields.Char(
        string="Frequency (printed)",
        help="Printed in the Frequency column of the client contract, e.g. Yearly Twice.",
    )
