# -*- coding: utf-8 -*-
{
    "name": "FM Subscription",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "Bill FM contracts as recurring subscriptions (sale_subscription)",
    "description": """
FM Platform — Subscription billing (brief §6.4, §10)
====================================================
Turns an FM contract into a recurring subscription using Odoo's standard
sale_subscription engine. The contract's product/service lines are the
recurring invoice lines, and the recurrence period is taken from the
contract's Billing Frequency.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_contract",
        "sale_subscription",
    ],
    "data": [
        "views/fm_contract_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
