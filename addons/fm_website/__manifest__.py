{
    'name': 'Aabaan Website',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Public website for Aabaan Services — pages, brand styling, enquiry routing',
    'description': """
Aabaan Services public website
==============================

Standard-first: this is the native **Website** app with Aabaan's pages and
brand styling on top. No custom controllers, no custom models, no page
framework of our own. Every page is an ordinary `website.page`, so staff
edit it in Odoo's own page editor — text, images and blocks — without
touching this module.

What the module contributes
---------------------------
* Four pages: Home, Services, Compliance, Contact.
* A brand stylesheet on web.assets_frontend that reuses the same design
  tokens as the FM backend (fm_branding), so the public site and the
  internal cockpit read as one company.
* A post-init hook that points the website's homepage at our Home page and
  adds the top menu entries — both guarded, both skipped if already set.

What it deliberately does NOT contribute
----------------------------------------
* No invented figures. Every claim on the site traces to the repository or
  the licences: the four emirates from fm_aabaan_config, the service lines
  from its product data, the permits from its compliance regimes. There is
  no "years of experience" or "customers served" counter, because no such
  number is on record here.
* No contact form model. The enquiry form posts to the native
  website_form → crm.lead pipeline when CRM is installed, and falls back to
  the phone and email numbers otherwise.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': [
        'website',
        'fm_branding',
    ],
    'data': [
        'views/templates.xml',
        'views/pages.xml',
        'data/website_pages.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'fm_website/static/src/scss/website.scss',
        ],
    },
    'post_init_hook': '_post_init_website',
    'installable': True,
    'application': False,
}
