# -*- coding: utf-8 -*-
{
    "name": "FM Field Service",
    "version": "19.0.2.1.0",
    "category": "Facility Management",
    "summary": "Facility Management on Odoo Field Service — FSM project, stages and asset-linked tasks",
    "description": """
FM Platform — Field Service re-base (foundation)
================================================
Standard-first re-base of the FM work-order engine onto Odoo **Field Service**
(``industry_fsm``). Instead of a bespoke ``fm.workorder`` state machine, work is
executed as native Field Service tasks (``project.task`` with ``is_fsm=True``):

* a ready-made **Field Service project** ("Facility Management") so every job
  lands in one FSM pipeline;
* **task stages** that mirror the old work-order state machine (Draft →
  Assigned → … → Signed Off) so nothing is lost in the transition;
* the FM domain fields — **asset, contract, severity, service line, work type** —
  grafted onto ``project.task`` by ``_inherit`` so FSM tasks carry the facility
  context.

This is the foundation the retired ``fm_workorder`` / ``fm_ppm`` / ``fm_sla`` /
``fm_integrations`` engines are being replaced by. Scheduling, SLA and calendar
are handled by native Odoo (recurrence, SLA policies, native calendar on tasks).
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "industry_fsm",
        "fm_asset",
        "fm_contract",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/fsm_stages.xml",
        "data/fsm_project.xml",
        "data/cron.xml",
        "views/project_task_views.xml",
        "views/fm_contract_views.xml",
        "views/menus.xml",
        "wizard/fm_contract_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
