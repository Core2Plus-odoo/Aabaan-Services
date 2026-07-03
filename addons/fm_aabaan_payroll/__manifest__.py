# -*- coding: utf-8 -*-
{
    "name": "FM Aabaan Payroll (UAE structure)",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "Standard UAE salary structure template — Basic / Housing / Transport + end-of-service gratuity accrual",
    "description": """
FM Platform — Aabaan UAE Payroll structure
==========================================
An **adjustable template** UAE monthly salary structure for Odoo Payroll:

* Contract **wage = total monthly package**, split into
  **Basic 60% · Housing 25% · Transport 15%** (standard UAE convention;
  edit the percentages to your policy).
* **Gross** and **Net** rules.
* An informational **End-of-Service Gratuity accrual** line
  (21 days' basic per year, accrued monthly) so you can provision EOSB.

You set real **wages** on each employee's contract and the **WPS bank / MOL
codes** in the UI. Percentages and rules here are a starting point — tune them
to Aabaan's actual policy. Requires Odoo **Payroll** (Enterprise).
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "hr_payroll",
    ],
    "data": [
        "data/payroll_structure.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
