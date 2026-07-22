# -*- coding: utf-8 -*-
{
    "name": "FM Branch",
    "version": "19.0.1.2.0",
    "category": "Facility Management",
    "summary": "Aabaan operating branches (emirate offices) on contracts, work orders and technicians",
    "description": """
FM Platform — Branches
======================
Records the service provider's own operating branches (e.g. Dubai, Sharjah,
Ajman offices) and lets every contract, work order and technician be assigned
to a branch, with grouping/filtering across the views.

Also adds the "state-wise" (per-branch/Emirate) dimension to Agreement
Templates (fm_contract), alongside the existing service-wise one — a
template can be scoped to a branch, a service line, both, or neither.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_fsm",
        "fm_documents",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/fm_branch_views.xml",
        "views/fm_contract_views.xml",
        "views/fm_contract_agreement_template_views.xml",
        "views/project_task_views.xml",
        "views/hr_employee_views.xml",
        "views/fm_documents_reports.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
