# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Website Theme',
    'version': '19.0.3.0.0',
    'post_init_hook': '_post_init_hook',
    'uninstall_hook': '_uninstall_hook',
    'category': 'Website/Website',
    'summary': 'Complete booking-first website in the approved Urban Company / Justlife style',
    'description': """
Code-defined website for Aaban Classic Building Cleaning L.L.C.:

- The booking-first page is the homepage itself (served at /). The previous
  homepage is parked, unpublished, at /home-classic — recoverable, never
  deleted. Old /home-v2 links 301-redirect to /.
- Full page set: /services overview, four service detail pages with
  rate-card pricing, /about (facts from the licence and the contract master
  sheet), /faq — plus the native /contactus form kept as the contact page.
- Site-wide branded footer (replaces website.footer_custom) with licence,
  TRN, service links and the corrected contact details (800 AABAN, both
  mobiles, infoaabanservices@gmail.com — no landline), and a fixed mobile
  action bar (Book / WhatsApp / Call) on every page.
- One SCSS asset carries the whole look (brand ink #17171a, orange #ef7d25),
  including navbar styling and the "Book a visit" menu entry as a button.
- The install hook / migration makes each website's main menu exactly:
  Home, Services (full-width mega menu: service tiles with prices, trust
  chips, AMC rail with contact CTA), About us, FAQ, Contact, Book a visit.
  Legacy internal menu items are removed (external links are kept) and
  all legacy pages are unpublished — recoverable from the page manager,
  never deleted.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['website', 'website_crm'],
    'data': [
        'views/layout.xml',
        'views/home_page.xml',
        'views/service_pages.xml',
        'views/services_index.xml',
        'views/about_page.xml',
        'views/faq_page.xml',
        'views/booking_page.xml',
        'views/contact_page.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'aabaan_website_theme/static/src/scss/aabaan_theme.scss',
        ],
    },
    'installable': True,
    'application': False,
}
