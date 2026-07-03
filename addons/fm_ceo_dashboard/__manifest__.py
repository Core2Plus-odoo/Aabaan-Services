# -*- coding: utf-8 -*-
{
    "name": "FM CEO Dashboard",
    "version": "19.0.1.0.1",
    "category": "Facility Management",
    "summary": "Executive (CEO) dashboard — portfolio value, contract health, operations, compliance risk, revenue",
    "description": """
FM Platform — CEO Dashboard
===========================
A single-page executive dashboard for Aabaan leadership, built for UAE facility
management: annual contract value and revenue (AED), active portfolio and
renewals pipeline, contract-health distribution, operations load by severity,
and compliance risk (expiring / expired certificates).

Implemented as a JavaScript-light OWL client action (KPI tiles + CSS bars, no
external chart library) reading live from the native records
(fm.contract / project.task / fm.compliance.certificate / account.move), scoped
to the user's companies. Menu is a non-default item, so it never blocks the FM
app from opening.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_contract",
        "fm_fsm",
        "fm_compliance",
    ],
    "data": [
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fm_ceo_dashboard/static/src/ceo_dashboard/ceo_dashboard.scss",
            "fm_ceo_dashboard/static/src/ceo_dashboard/ceo_dashboard.js",
            "fm_ceo_dashboard/static/src/ceo_dashboard/ceo_dashboard.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
