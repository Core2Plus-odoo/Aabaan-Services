# -*- coding: utf-8 -*-
{
    "name": "FM CEO Dashboard (retired)",
    "version": "19.0.9.0.0",
    "category": "Facility Management",
    "summary": "Retired \u2014 superseded by the standalone Command Centre app",
    "description": """
FM CEO Dashboard \u2014 retired
==========================

One of three executive dashboards that sat side by side under the FM app,
two of them literally named "CEO Dashboard". The Command Centre answers
everything this one did (portfolio value, contract health, operations load,
compliance risk) and more, from one screen.

This is an empty stub. It exists only so an installed database still loads
while ``migrations/19.0.9.0.0/pre-migration.py`` removes the module's
residual records (menus, actions, views, model metadata) in FK-safe order.
Uninstall it from Apps once the production upgrade has run, then the stub
itself can be deleted from source. See CLAUDE.md section 5.
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
