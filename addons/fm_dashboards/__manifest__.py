# -*- coding: utf-8 -*-
{
    "name": "FM Dashboards",
    "version": "19.0.1.0.1",
    "category": "Facility Management",
    "summary": "Executive dashboard (OWL) — KPIs, at-risk contracts, top performers, service mix",
    "description": """
FM Platform — Executive Dashboard (brief §7.1)
==============================================
A branded OWL client-action dashboard for management: KPI tiles (revenue,
active contracts, SLA compliance, open criticals, CSAT), an at-risk contracts
table, a technician leaderboard and the service mix — all read live from
fm.workorder / fm.contract, scoped to the user's companies.

Built from the brief's component spec and the shared --fm-* design tokens.
ApexCharts trend/column charts (brief §7.1) are a follow-up; this ships the
KPI tiles, tables and CSS bars.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_sla",
    ],
    "data": [
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fm_dashboards/static/src/exec_dashboard/exec_dashboard.scss",
            "fm_dashboards/static/src/exec_dashboard/exec_dashboard.js",
            "fm_dashboards/static/src/exec_dashboard/exec_dashboard.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
