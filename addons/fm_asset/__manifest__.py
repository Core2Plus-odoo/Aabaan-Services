# -*- coding: utf-8 -*-
{
    "name": "FM Asset",
    "version": "19.0.1.0.3",
    "category": "Facility Management",
    "summary": "Asset registry: hierarchy, criticality, locations and QR codes",
    "description": """
FM Platform — Asset Registry
============================
Asset registry for the FM Platform (brief §5.2). Composes with the standard
Maintenance app: ``fm.asset`` reuses ``maintenance.equipment`` via prototype
inheritance, adding FM-specific structure (category service-lines, location
hierarchy, criticality, lifecycle state, QR identity).

Maps to the ``assets.html`` prototype (brief §7.5); the OWL stats hero is added
in a later phase once the prototype files are available.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_branding",
        "maintenance",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_sequence.xml",
        "views/fm_asset_category_views.xml",
        "views/fm_asset_location_views.xml",
        "views/fm_asset_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
