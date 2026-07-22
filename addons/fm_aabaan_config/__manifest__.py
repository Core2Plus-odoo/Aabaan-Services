# -*- coding: utf-8 -*-
{
    "name": "FM Aabaan Configuration",
    "version": "19.0.1.3.0",
    "category": "Facility Management",
    "summary": "Aabaan-ready seed data: branches, service catalogue, asset categories and UAE compliance regimes",
    "description": """
FM Platform — Aabaan configuration & seed data
==============================================
Turns the generic FM platform into an out-of-the-box **Aabaan Services** setup:

* **Branches** — Aabaan's UAE operating offices (Dubai, Sharjah, Ajman, Abu Dhabi).
* **Asset categories** — one per Aabaan service line (pest control, cleaning,
  water-tank cleaning, AC/HVAC, plumbing) with sensible PPM cadences.
* **UAE compliance regimes** — Dubai Municipality pest-control permit, water-tank
  cleaning & disinfection certificate, Civil Defence, DEWA — with task templates.

All records are ``noupdate`` seed data so administrators can edit them freely.
No custom models — everything targets the native/thin FM models.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_branch",
        "fm_compliance",
        "sale",
    ],
    "data": [
        "data/fm_branch_data.xml",
        "data/fm_asset_category_data.xml",
        "data/fm_compliance_regime_data.xml",
        "data/product_data.xml",
        "data/fm_contract_agreement_template_data.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
