# -*- coding: utf-8 -*-
{
    "name": "FM Reports",
    "version": "19.0.1.0.1",
    "category": "Facility Management",
    "summary": "Reports hub (OWL) — grouped catalog of operational, financial and compliance views",
    "description": """
FM Platform — Reports Hub (brief §7.7)
======================================
An OWL card catalog grouping the platform's analysis views into Operational,
Financial and Compliance sections; each card opens the matching action.
Built from the §7.7 spec and the shared --fm-* design tokens.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_workorder",
        "fm_compliance",
        "fm_ppm",
    ],
    "data": [
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fm_reports/static/src/reports_hub/reports_hub.scss",
            "fm_reports/static/src/reports_hub/reports_hub.js",
            "fm_reports/static/src/reports_hub/reports_hub.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
