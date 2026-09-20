# -*- coding: utf-8 -*-
{
    "name": "Aabaan Executive Dashboard (retired)",
    "version": "19.0.9.0.0",
    "category": "Facility Management",
    "summary": "Retired \u2014 superseded by the standalone Command Centre app",
    "description": """
Aabaan Executive Dashboard \u2014 retired
====================================

The second of the three executive dashboards, superseded by the Command
Centre's finance, expenses and cash tabs. Its two stored fields were not
dashboard code and have been moved into fm_branch, which owns them:
account.move.branch_id and fm.branch.monthly_revenue_target. The columns
and their data are untouched.

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
