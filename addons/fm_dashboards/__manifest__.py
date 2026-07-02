# -*- coding: utf-8 -*-
{
    "name": "FM Dashboards",
    "version": "19.0.2.0.0",
    "category": "Facility Management",
    "summary": "Native FM dashboards — Operations (work orders) and Contracts graph/pivot analysis",
    "description": """
FM Platform — Dashboards
========================
Native, JavaScript-free management dashboards built from standard Odoo
graph/pivot/kanban actions over the native records:

* **Operations Dashboard** — Field Service work orders (project.task) by service
  line, severity, stage and branch.
* **Contracts Dashboard** — AMC / break-fix contracts by state, health and value.

Replaces the earlier OWL client-action dashboard, which depended on a custom JS
bundle; native actions cannot fail with a client-action registry error and need
no asset rebuild.
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
    "installable": True,
    "application": False,
    "auto_install": False,
}
