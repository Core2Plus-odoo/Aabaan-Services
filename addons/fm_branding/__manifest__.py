# -*- coding: utf-8 -*-
{
    "name": "FM Branding",
    "version": "19.0.1.0.0",
    "category": "Facility Management",
    "summary": "Foundation module: theme tokens, branding settings and FM security groups",
    "description": """
FM Platform — Branding & Foundation
===================================
Foundation module for the C2P Facility Management platform (see
docs/IMPLEMENTATION_BRIEF.md). Provides:

* Data-driven branding configuration (logo, colours, currency, VAT, compliance
  country) on res.company, surfaced in Settings — so a tenant can rebrand
  without forking the codebase (brief §2.3, §5.1).
* The shared design tokens from the prototypes, applied to the Odoo backend
  via the web.assets_backend bundle (brief §2.4, §3.1).
* The FM role hierarchy of security groups every other fm_* module builds on
  (brief §8.1).

This is the only fm_* module with application=True; all others depend on it.
""",
    "author": "C2P Consultants FZC LLC",
    "website": "https://c2p.ae",
    "license": "OPL-1",
    "depends": [
        "base",
        "base_setup",
        "mail",
    ],
    "data": [
        "security/security.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fm_branding/static/src/scss/_tokens.scss",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
