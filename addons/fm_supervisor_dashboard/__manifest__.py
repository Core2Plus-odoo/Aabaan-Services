# -*- coding: utf-8 -*-
{
    "name": "FM Supervisor Dashboard",
    "version": "19.0.1.0.2",
    "category": "Facility Management",
    "summary": "Supervisor visit board — the week's work orders at a glance, colour-coded by status",
    "description": """
FM Platform — Supervisor Dashboard
==================================
An extremely simple visit board for supervisors: the whole week's work orders
laid out Mon–Sun as customer chips, colour-coded by status (today / scheduled /
overdue / done / cancelled), with a KPI strip (today, overdue, unassigned, week
total, done). Filter by technician, service line or branch, jump week to week,
and click any visit to open it. Everything is visible without drilling down.

JavaScript-light OWL (CSS chips, no external calendar library); the menu is a
non-default item so a JS issue can never block the FM app from opening.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_fsm",
    ],
    "data": [
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fm_supervisor_dashboard/static/src/supervisor/supervisor_dashboard.scss",
            "fm_supervisor_dashboard/static/src/supervisor/supervisor_dashboard.js",
            "fm_supervisor_dashboard/static/src/supervisor/supervisor_dashboard.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
