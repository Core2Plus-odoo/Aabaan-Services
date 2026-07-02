# -*- coding: utf-8 -*-
{
    "name": "FM Contract",
    "version": "19.0.1.2.0",
    "category": "Facility Management",
    "summary": "AMC contracts, SLA rules, scope and renewal lifecycle",
    "description": """
FM Platform — Contracts (brief §5.5)
====================================
AMC / break-fix / project contracts. Composes with ``sale.order`` for billing
(``_inherits``) and carries FM scope (covered assets, service inclusions/
exclusions), SLA rules, penalties and a renewal lifecycle.

``workorder_ids`` and the data-driven health score (which need work-order and
CSAT history) are added by ``fm_workorder`` / ``fm_sla`` once those modules
land — see README.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_asset",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_sequence.xml",
        "views/fm_contract_service_item_views.xml",
        "views/fm_sla_rule_views.xml",
        "views/fm_contract_views.xml",
        "views/fm_customer_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
