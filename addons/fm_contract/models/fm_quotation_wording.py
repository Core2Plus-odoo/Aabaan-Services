# -*- coding: utf-8 -*-
import re

from markupsafe import Markup, escape

from odoo import Command, api, fields, models

from .fm_contract_agreement_template import LINE_KINDS

QUOTE_TABLE_COLUMNS = ("unit", "frequency", "subtotal", "summary")


class FmQuotationWordingLine(models.Model):
    """One block of a printed quotation, in the client's own wording.

    Held twice, like the agreement wording: on the quotation template it
    is the standard text; on the order it is that order's own copy,
    edited freely without touching the template.
    """

    _name = "fm.quotation.wording.line"
    _description = "FM Quotation Wording"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "sale.order.template", string="Quotation Template", ondelete="cascade", index=True)
    order_id = fields.Many2one(
        "sale.order", string="Quotation", ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(LINE_KINDS, default="article", required=True)
    name = fields.Char(string="Heading", required=True)
    body_html = fields.Html(string="Body (formatted)")

    def _fm_copy_values(self):
        return [{"sequence": line.sequence, "kind": line.kind, "name": line.name,
                 "body_html": line.body_html} for line in self]


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    fm_quote_client_layout = fields.Boolean(
        string="Client Quotation Layout",
        help="Print the quotation the way the client writes it: the wording "
             "below, in order, with the priced lines where the Price Table "
             "line sits.")
    fm_quote_columns = fields.Char(
        string="Quotation Table Columns", default="unit,frequency,subtotal",
        help="After Description, comma-separated: unit, frequency, subtotal, summary.")
    fm_quote_per_year = fields.Boolean(
        string="'For 1 Year' Labels",
        help="Label the subtotal 'Subtotal For 1 Year' and the units "
             "'Total Units For 1 Year'.")
    fm_quote_company_block = fields.Boolean(
        string="Company Block in Header",
        help="Print the company's name, address, e-mail, phone and TRN above "
             "the customer, as the client's newer quotations do.")
    fm_quote_line_ids = fields.One2many(
        "fm.quotation.wording.line", "template_id", string="Quotation Wording", copy=True)

    def _fm_preview_html(self, value):
        """The wording with each placeholder shown as a marker naming it,
        since a template has no quotation to fill it from."""
        if not value:
            return Markup("")
        chip = ('<span style="background:#FFF2C2;border:1px dashed #D2551E;color:#8A3708;'
                'font-weight:bold;padding:1px 6px;border-radius:3px;">\u270e %s</span>')
        return Markup(re.sub(r"\{\{\s*([A-Z_]+)\s*\}\}",
                             lambda m: chip % escape(m.group(1)), str(value)))

    def _fm_quote_columns(self):
        self.ensure_one()
        cols = [c.strip() for c in (self.fm_quote_columns or "").split(",")]
        return [c for c in cols if c in QUOTE_TABLE_COLUMNS]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    fm_quote_client_layout = fields.Boolean(
        related="sale_order_template_id.fm_quote_client_layout")
    fm_quote_columns = fields.Char(related="sale_order_template_id.fm_quote_columns")
    fm_quote_per_year = fields.Boolean(related="sale_order_template_id.fm_quote_per_year")
    fm_quote_company_block = fields.Boolean(related="sale_order_template_id.fm_quote_company_block")
    fm_quote_line_ids = fields.One2many(
        "fm.quotation.wording.line", "order_id", string="Quotation Wording", copy=True)

    @api.onchange("sale_order_template_id")
    def _onchange_fm_quote_wording(self):
        self.fm_quote_line_ids = [Command.clear()] + [
            Command.create(vals)
            for vals in self.sale_order_template_id.fm_quote_line_ids._fm_copy_values()]

    def _fm_apply_quote_wording(self):
        for order in self:
            order.fm_quote_line_ids = [Command.clear()] + [
                Command.create(vals)
                for vals in order.sale_order_template_id.fm_quote_line_ids._fm_copy_values()]

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        # An order made outside the form (import, RPC, CRM) gets the wording
        # the form's onchange would have given it.
        for order, vals in zip(orders, vals_list):
            if order.sale_order_template_id and "fm_quote_line_ids" not in vals:
                order._fm_apply_quote_wording()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if "sale_order_template_id" in vals and "fm_quote_line_ids" not in vals:
            self._fm_apply_quote_wording()
        return res

    def _fm_quote_columns(self):
        self.ensure_one()
        cols = [c.strip() for c in (self.fm_quote_columns or "").split(",")]
        return [c for c in cols if c in QUOTE_TABLE_COLUMNS]

    def _fm_quote_values(self):
        self.ensure_one()
        values = dict(self._fm_client_values())
        contact = self._fm_client_contact()
        values.update({
            "TOTAL": self._fm_client_money(self.amount_total),
            "TOTAL_WORDS": self._fm_client_amount_in_words()[:-len(" Only")],
            "CONTACT_SALUTATION": re.sub(r"^(mr|mrs|ms|miss|dr)\.?\s+", "", contact.name or "", flags=re.I),
            "VALID_UNTIL": self._fm_client_date(self.validity_date),
        })
        return values
