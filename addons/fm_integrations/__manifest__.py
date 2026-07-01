# -*- coding: utf-8 -*-
{
    "name": "FM Integrations",
    "version": "19.0.1.2.0",
    "category": "Facility Management",
    "summary": "Link FM work orders to Odoo standard apps (Calendar, …) and import master data",
    "description": """
FM Platform — Standard integrations (brief §10)
===============================================
Links FM work orders to native Odoo functionality. This first drop syncs every
scheduled work order to the standard **Calendar** (calendar.event) so the
assigned technician sees their jobs in the Calendar app with reminders, and
reschedules flow both ways via the event.

Master Data Import
==================
Allows importing master data (customers, products, employees, accounts, etc.)
from external Odoo instances via XML-RPC API.

Subscription / recurring-billing integration is added next once the recurring
plan is chosen.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_workorder",
        "calendar",
        "hr",
        "account",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/fm_workorder_views.xml",
        "views/odoo_master_data_import_views.xml",
        "views/odoo_master_data_import_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
