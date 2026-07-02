# -*- coding: utf-8 -*-
{
    "name": "FM Service Materials",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "Bill of materials per service — which materials/consumables each service uses per visit",
    "description": """
FM Platform — Service Materials (composition)
=============================================
Defines, for each **service product**, the **materials/consumables it uses per
visit** (a lightweight bill of materials). This is the digital form of the
Service ↔ Material Composition sheet, and the basis for anticipating material
requirements and consumption from the scheduled visit calendar.

* ``fm.service.material`` — a composition line: service product → material
  product, quantity per visit, unit, billable, notes.
* A **Materials** tab on the service product form to maintain the composition.
* A **Service Materials** menu (list / pivot) under FM Configuration to review
  the whole catalogue at once.

Consumption capture on the visit and a live material forecast
(planned visits × qty per visit) build on this in a follow-up.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "product",
        "uom",
        "fm_fsm",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/fm_service_material_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
