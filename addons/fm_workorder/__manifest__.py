# -*- coding: utf-8 -*-
{
    "name": "FM Work Order",
    "version": "19.0.1.1.0",
    "category": "Facility Management",
    "summary": "Work orders: state machine, checklist, parts, labor and sign-off",
    "description": """
FM Platform — Work Orders (brief §5.3, §6.1)
============================================
The heart of the platform. ``fm.workorder`` composes with
``maintenance.request`` and adds the FM state machine (draft → assigned →
acknowledged → arrived → in_progress → completed → signed_off, with
awaiting_parts / awaiting_customer branches and cancelled), checklist, parts,
labor and customer sign-off + CSAT.

Also extends ``fm.contract`` with ``workorder_ids`` (resolving the contract↔WO
circular reference) and provides checklist templates used by ``fm_ppm``.

The OWL work-order form / kanban (brief §7.3, §7.4) are added once the
``/prototypes/`` files are available; standard views ship here.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_contract",
        "hr",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_sequence.xml",
        "views/fm_checklist_template_views.xml",
        "views/fm_workorder_views.xml",
        "views/fm_contract_views.xml",
        "views/menus.xml",
    ],
    "demo": [
        "data/demo.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
