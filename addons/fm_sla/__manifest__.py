# -*- coding: utf-8 -*-
{
    "name": "FM SLA & Health",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "SLA breach detection, contract health scoring and WO->invoice automation",
    "description": """
FM Platform — SLA, Health & Billing automation (brief §6.2, §6.4, §6.5)
=======================================================================
Adds to work orders the SLA response/resolution actuals and breach status
(with a 5-minute watchdog cron), computes contract health scores nightly, and
generates the customer invoice when a billable work order is signed off.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_workorder",
    ],
    "data": [
        "data/ir_cron.xml",
        "views/fm_workorder_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
