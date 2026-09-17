from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_website_theme import _apply_site_structure


def migrate(cr, version):
    """Services mega menu release: the Services entry becomes a native
    full-width mega menu (branded panel, service tiles, AMC rail)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_site_structure(env)
