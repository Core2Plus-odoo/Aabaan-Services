from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Same as the install hook: point the homepage at the booking-first
    page for databases where the module was installed before 19.0.1.1.0."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Website = env['website']
    if 'homepage_url' in Website._fields:
        Website.search([]).write({'homepage_url': '/home-v2'})
