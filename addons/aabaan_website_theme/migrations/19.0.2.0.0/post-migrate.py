from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_website_theme import _apply_site_structure


def migrate(cr, version):
    """Full site overhaul: /home-v2 becomes the page at `/` (old homepage
    parked at /home-classic), homepage pointer cleared, main menu completed
    with Services / About / FAQ / Book entries."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_site_structure(env)
