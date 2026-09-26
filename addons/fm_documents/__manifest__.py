# -*- coding: utf-8 -*-
{
    "name": "FM Documents",
    "version": "19.0.3.0.0",
    "category": "Facility Management",
    "summary": "Branded PDF documents — job sheet, quotation, contract, tax invoice",
    "description": """
FM Platform — Document layouts
==============================

Branded A4 PDFs on Odoo's standard letterhead, which already carries the
company name, address, logo and TRN — so they follow UAE practice without a
second letterhead of our own to keep in step.

* Work Order service report (job sheet): checklist, parts, labour, totals in
  AED, customer sign-off and CSAT.
* Quotation: the pre-contract proposal — scope, treatment, terms, pricing
  with the VAT breakdown.
* Service Agreement: the signable contract — numbered Articles, pricing and
  signature blocks.
* Tax Invoice: every mandatory field of Federal Decree-Law No. 8 of 2017 and
  Cabinet Decision 52, plus a per-tax breakdown, the total in words, the
  reverse-charge notice where the fiscal position actually calls for it, and
  the company's real bank details where it has them.

The Tax Invoice is a report action of its own. Odoo's native invoice print is
left untouched — a branded document is never an overwrite of a core record.

Customer invoices also gain a Document Audit Trail tab, built only from events
the system can prove: created and posted timestamps, a mail that really was
sent, payments really reconciled, credit notes really issued.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "account",
        "fm_fsm",
        "fm_compliance",
    ],
    "data": [
        "reports/project_task_report.xml",
        "reports/fm_quotation_report.xml",
        "reports/fm_contract_report.xml",
        "reports/fm_certificate_report.xml",
        "reports/fm_tax_invoice_report.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
