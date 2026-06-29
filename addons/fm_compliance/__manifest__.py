# -*- coding: utf-8 -*-
{
    "name": "FM Compliance",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "Regulatory regimes, compliance certificates and expiry watchdog",
    "description": """
FM Platform — Compliance (brief §5.6, §6.6)
===========================================
GCC regulatory regimes (Civil Defence, DEWA, Municipality, …), compliance
certificates per asset/location, and a daily watchdog that raises compliance
work orders ahead of certificate expiry and flags expired certificates.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_workorder",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/fm_compliance_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
