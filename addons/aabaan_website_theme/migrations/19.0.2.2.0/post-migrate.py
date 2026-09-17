from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_website_theme import _apply_site_structure


def migrate(cr, version):
    """Menu bar cleanup release: the top menu becomes exactly the defined
    set (legacy Home/Services/Coverage/About/Contact items removed) and all
    legacy pages are unpublished — recoverable from the page manager."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_site_structure(env)
