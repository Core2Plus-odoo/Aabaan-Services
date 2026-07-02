# -*- coding: utf-8 -*-
{
    "name": "FM Planned Maintenance (retired)",
    "version": "19.0.9.0.0",
    "category": "Facility Management",
    "summary": "Retired — superseded by native Odoo Field Service. Empty placeholder kept so an installed database can load and cleanly uninstall it.",
    "description": """
This module has been retired by the Field Service re-base. Its functionality is
now provided by native Odoo Field Service (project.task), SLA policies,
recurrence and the native calendar.

It is intentionally left as an **empty** module so that databases where it was
already installed can load without the "module not loaded" error, drop its old
menus/views on upgrade, and be uninstalled cleanly from Apps when convenient.
Do not build on it.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": ["base"],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
