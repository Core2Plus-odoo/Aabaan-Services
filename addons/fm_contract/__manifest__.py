# -*- coding: utf-8 -*-
{
    "name": "FM Contract",
    "version": "19.0.3.0.0",
    "category": "Facility Management",
    "summary": "AMC contracts, SLA rules, scope and renewal lifecycle",
    "description": """
FM Platform — Contracts (brief §5.5)
====================================
A contract is a sale order. This module adds the facility-management layer
to ``sale.order``: covered assets, service inclusions/exclusions, SLA rules,
penalty clauses, a renewal lifecycle that starts when the order is confirmed,
and the wording printed on the customer's signed agreement.

The older ``fm.contract`` model (which wrapped a sale order by delegation) is
still here and still readable, but nothing creates it any more; it is being
retired. Both read one definition of the printed-agreement rules,
``fm.agreement.mixin``.

Visits/work orders are native Field Service tasks linked by ``fm_fsm``;
contract health is maintained by the account manager.
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
        "views/fm_contract_agreement_template_views.xml",
        "views/fm_sla_rule_views.xml",
        "views/fm_contract_views.xml",
        "views/sale_order_views.xml",
        "views/fm_customer_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
