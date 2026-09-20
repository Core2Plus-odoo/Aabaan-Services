# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES

from .sale_order import BILLING_FREQUENCIES, CONTRACT_TYPES


class SaleOrderTemplate(models.Model):
    """A quotation template that also carries the FM contract profile.

    Odoo's Quotation Templates already hold the part of a contract that
    repeats: the priced service lines, the terms and conditions, the
    validity, whether a signature is required. What they do not hold is
    everything FM adds — the service line, the term, how often a visit
    happens, which wording gets printed — so writing the twentieth pest
    control AMC of the month still meant filling in the same fifteen
    fields by hand.

    This puts those on the template too, so a contract is: pick the
    customer, pick the template, add the site's assets, confirm.

    Defaults, not a straitjacket. Every field the template fills on the
    order stays editable there (the computes are ``readonly=False``), so
    a contract that differs from the standard shape is still one edit
    away rather than a reason to start from a blank order.
    """

    _inherit = "sale.order.template"

    fm_is_contract_profile = fields.Boolean(
        string="FM Contract Profile",
        help="Orders created from this template are FM contracts: they get "
             "the term, visit schedule and printed agreement below, and they "
             "appear under Facility Management → Contracts.",
    )
    fm_service_line = fields.Selection(
        SERVICE_LINES, string="Service",
        help="What service these contracts cover — also picks the printed "
             "agreement wording when no template is named below.",
    )
    fm_contract_type = fields.Selection(
        CONTRACT_TYPES, string="Contract Type", default="amc_comprehensive",
    )
    fm_term_months = fields.Integer(
        string="Contract Term (months)", default=12,
        help="How long these contracts run. The end date is filled in from "
             "the start date plus this term.",
    )
    fm_billing_frequency = fields.Selection(
        BILLING_FREQUENCIES, string="Billing Frequency", default="monthly",
    )
    fm_account_manager_id = fields.Many2one(
        "res.users", string="Default Account Manager",
        help="Left blank, the contract falls to whoever raises it.",
    )
    fm_agreement_template_id = fields.Many2one(
        "fm.contract.agreement.template", string="Agreement Wording",
        help="Wording for the printed Quotation and Service Agreement. Left "
             "blank, it is still suggested from the service line and branch.",
    )
