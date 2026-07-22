# -*- coding: utf-8 -*-
{
    "name": "FM Documents",
    "version": "19.0.1.5.2",
    "category": "Facility Management",
    "summary": "Branded PDF documents (work order job sheet, quotation, contract) — UAE-ready",
    "description": """
FM Platform — Document layouts (brief §9.5)
===========================================
Branded A4 PDF documents on Odoo's standard letterhead (which carries the
company name, address, logo and TRN/VAT — so they follow UAE practice):
- Work Order service report (job sheet) with checklist, parts, labor, totals
  in AED and the customer sign-off + CSAT.
- Quotation — pre-contract proposal (scope, treatment, terms, pricing + VAT).
- Service Agreement — signable legal contract (numbered Articles, pricing,
  signature blocks).

Tax invoices use Odoo's standard FTA-compliant Tax Invoice (account.move):
set the company TRN in its VAT field and the 5% tax for full compliance.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_fsm",
        "fm_compliance",
    ],
    "data": [
        "reports/project_task_report.xml",
        "reports/fm_quotation_report.xml",
        "reports/fm_contract_report.xml",
        "reports/fm_certificate_report.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
