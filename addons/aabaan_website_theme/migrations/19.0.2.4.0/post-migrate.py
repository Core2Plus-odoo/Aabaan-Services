from odoo import SUPERUSER_ID, api

from odoo.addons.aabaan_website_theme import _apply_site_structure


def migrate(cr, version):
    """Menu de-duplication release: the top menu is wiped and rebuilt to
    exactly the defined set. '#'-URL items (old dropdown parents) are now
    treated as internal and removed too — they were the survivors that
    produced the duplicated Services entries."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_site_structure(env)
