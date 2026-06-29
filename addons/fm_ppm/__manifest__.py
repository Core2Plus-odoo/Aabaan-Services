# -*- coding: utf-8 -*-
{
    "name": "FM PPM",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "Planned preventive maintenance schedules with automatic work-order generation",
    "description": """
FM Platform — Preventive Maintenance (brief §5.4, §6 PPM generation)
====================================================================
Time/meter-based PPM schedules per asset. A daily cron generates PPM work
orders ahead of the due date using the schedule's checklist template.
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
        "views/fm_ppm_schedule_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
