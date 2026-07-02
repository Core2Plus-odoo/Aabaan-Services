# -*- coding: utf-8 -*-
{
    "name": "FM Master Data Import",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "Import master data (customers, products, employees, accounts) from another Odoo via XML-RPC",
    "description": """
FM Platform — Master Data Import
================================
Import master data from an **external / legacy Odoo instance** into this
database over the standard **XML-RPC API**, run from inside your own server
(so it works regardless of where this container can reach — the import runs on
the Odoo backend, not a sandbox).

Two entry points, both under **FM → Configuration**:

* **Master Data Import** — a saved configuration (source URL / database / login
  / API key + which data to import); re-runnable.
* **Import Master Data** — a one-shot wizard with the same logic, no stored
  credentials.

Imports (idempotent, de-duplicated): ``res.partner`` (customers/vendors),
``product.template`` / ``product.category``, ``hr.employee``, optionally
``account.account`` / ``account.journal`` and company data.

Salvaged and modernised for Odoo 19 from the original master-data-import work.
Standalone: depends only on standard apps, so it installs cleanly on the
re-based FM platform.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "base",
        "sale",
        "hr",
        "account",
        "fm_fsm",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/odoo_master_data_import_views.xml",
        "views/odoo_master_data_import_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
