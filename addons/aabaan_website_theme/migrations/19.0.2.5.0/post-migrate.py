from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_website_theme import _apply_site_structure


def migrate(cr, version):
    """Booking + contact release: module pages now own /booking (new
    branded booking form) — legacy pages clashing with ANY module page URL
    (/booking, /about, …) are parked at <url>-classic so website-specific
    old pages can no longer shadow the new generic ones."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_site_structure(env)
