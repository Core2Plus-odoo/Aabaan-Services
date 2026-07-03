# -*- coding: utf-8 -*-
{
    "name": "FM Aabaan Setup (UAE base config)",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "Safe base configuration for Aabaan: UAE working week (Mon–Fri), HR departments & job positions",
    "description": """
FM Platform — Aabaan base configuration
=======================================
Non-destructive base configuration that is safe to install on a live company:

* a **UAE Standard working calendar** (Mon–Fri, 8h/day) set as the company
  default if the company still uses the generic 40h week;
* **HR departments** and **job positions** for a UAE FM operation;
* sets the company **country to United Arab Emirates** if unset.

It deliberately does **not** touch accounting (chart of accounts, taxes) or run
payroll — those are configured per the runbook (``docs/UAE_SETUP_RUNBOOK.md``)
because they depend on your live data and figures. See that runbook for the
full basic + advanced (localization, VAT/TRN, payroll, WPS, leaves) setup.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "hr",
        "fm_branding",
    ],
    "data": [
        "data/resource_calendar.xml",
        "data/hr_data.xml",
    ],
    "post_init_hook": "_post_init_apply",
    "installable": True,
    "application": False,
    "auto_install": False,
}
