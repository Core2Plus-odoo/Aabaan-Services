from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_website_theme import _apply_site_structure


def migrate(cr, version):
    """Re-apply the homepage takeover with the beautification release, so
    the booking-first site is what opens at `/` even if the previous
    switch-over was skipped or a page was re-created at `/` since."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_site_structure(env)
