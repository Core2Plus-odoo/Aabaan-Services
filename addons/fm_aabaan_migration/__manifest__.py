# -*- coding: utf-8 -*-
{
    "name": "FM Aabaan Migration",
    "version": "19.0.1.1.0",
    "category": "Facility Management",
    "summary": "One-click migration of aabaan contracts/visits into the FM Platform",
    "description": """
Migrates legacy aabaan_service_scheduler data into the FM Platform:
- aabaan.service.contract -> fm.contract (+ one 'service site' fm.asset each,
  since FM is asset-centric and aabaan is not)
- aabaan.service.visit -> fm.workorder
Customers (res.partner) are shared, so they are reused, not duplicated.
The wizard is idempotent: already-migrated records are skipped on re-run.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "fm_workorder",
        "aabaan_service_scheduler",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/migration_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
