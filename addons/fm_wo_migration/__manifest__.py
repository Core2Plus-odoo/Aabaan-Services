# -*- coding: utf-8 -*-
{
    "name": "FM Work Order → FSM Migration",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "One-off converter: legacy fm.workorder records → native Field Service tasks",
    "description": """
FM Platform — legacy Work Order converter
=========================================
The Field Service re-base retired the custom ``fm.workorder`` model. Any rows
created under it are converted here into native Field Service tasks
(``project.task`` in the FM project), so history is preserved before the old
modules are uninstalled.

Reads the leftover ``fm_workorder`` table by SQL (the Python model is gone once
``fm_workorder`` is removed, but the table survives until the module is
uninstalled), and creates matching ``project.task`` records. Idempotent via
``project.task.legacy_workorder_id``.

Run **Facility Management → Configuration → Convert Legacy Work Orders**, verify
the count, then uninstall fm_workorder / fm_ppm / fm_sla / fm_integrations. This
converter module can then be uninstalled too.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_fsm",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/convert_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
