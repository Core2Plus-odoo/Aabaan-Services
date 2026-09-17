from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_website_theme import _apply_site_structure


def migrate(cr, version):
    """Footer and header tidy-up: hide Odoo's native copyright bar, which
    duplicates the branded footer and still showed the stock placeholder
    "Copyright (c) Company name", and drop the native "Contact Us" header
    button, which competed with "Book a visit". Both are done by flipping
    the views Odoo's own builder toggles, so this only needs the existing
    idempotent switch-over to run again."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_site_structure(env)
