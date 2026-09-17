from odoo.tests import TransactionCase, tagged

from odoo.addons.aabaan_website_theme import (
    KEEP_PUBLISHED_URLS,
    SITE_MENUS,
    _apply_site_structure,
    _owned_menu_urls,
)

PAGES = [
    ('aabaan_website_theme.page_home_v2', '/'),
    ('aabaan_website_theme.page_rec_services_index', '/services'),
    ('aabaan_website_theme.page_rec_svc_pest', '/services/pest-control'),
    ('aabaan_website_theme.page_rec_svc_tank', '/services/water-tank'),
    ('aabaan_website_theme.page_rec_svc_termite', '/services/anti-termite'),
    ('aabaan_website_theme.page_rec_svc_cleaning', '/services/deep-cleaning'),
    ('aabaan_website_theme.page_rec_about', '/about'),
    ('aabaan_website_theme.page_rec_faq', '/faq'),
    ('aabaan_website_theme.page_rec_booking', '/booking'),
    ('aabaan_website_theme.page_rec_booking_thanks', '/booking-thanks'),
]


@tagged('post_install', '-at_install')
class TestWebsiteOverhaul(TransactionCase):

    def test_pages_published_at_expected_urls(self):
        for xmlid, url in PAGES:
            page = self.env.ref(xmlid)
            self.assertEqual(page.url, url)
            self.assertTrue(page.is_published)

    def test_booking_first_page_is_the_homepage(self):
        home = self.env.ref('aabaan_website_theme.page_home_v2')
        self.assertEqual(home.url, '/')
        others = self.env['website.page'].search(
            [('url', '=', '/'), ('id', '!=', home.id)])
        self.assertFalse(
            others, "any pre-existing homepage must be parked at /home-classic")
        Website = self.env['website']
        if 'homepage_url' in Website._fields:
            self.assertFalse(
                Website.search([]).filtered('homepage_url'),
                "homepage_url must be cleared so / serves the page itself")

    def test_top_menu_is_exactly_the_defined_set(self):
        _apply_site_structure(self.env)
        # Names, not URLs: Odoo may rewrite a mega menu's URL to '#'.
        expected = {name for name, _, _, _ in SITE_MENUS}
        for website in self.env['website'].search([]):
            root = self.env['website.menu'].search(
                [('parent_id', '=', False), ('website_id', '=', website.id)],
                limit=1)
            if not root:
                continue
            internal = root.child_id.filtered(
                lambda m: not (m.url or '').startswith(
                    ('http://', 'https://', 'mailto:', 'tel:')))
            self.assertEqual(set(internal.mapped('name')), expected)
            self.assertEqual(len(internal), len(SITE_MENUS),
                             "no duplicate top-level menu items allowed")

    def test_legacy_pages_unpublished(self):
        _apply_site_structure(self.env)
        ours = self.env['ir.model.data'].search([
            ('module', '=', 'aabaan_website_theme'),
            ('model', '=', 'website.page'),
        ]).mapped('res_id')
        strays = self.env['website.page'].search([
            ('id', 'not in', ours),
            ('url', 'not in', KEEP_PUBLISHED_URLS),
            ('is_published', '=', True),
        ])
        self.assertFalse(
            strays, f"legacy pages still published: {strays.mapped('url')}")

    def test_no_page_shadows_a_module_page(self):
        """A legacy page sharing a module page's URL would shadow it in
        routing — the parking sweep must clear every clash."""
        Page = self.env['website.page']
        legacy = Page.create({
            'name': 'Old booking', 'url': '/booking',
            'view_id': self.env.ref('aabaan_website_theme.page_booking').id,
            'is_published': True,
        })
        _apply_site_structure(self.env)
        self.assertEqual(legacy.url, '/booking-classic')
        self.assertFalse(legacy.is_published)
        for _xmlid, url in PAGES:
            ours = self.env.ref(_xmlid)
            clashes = Page.search(
                [('url', '=', url), ('id', '!=', ours.id)])
            self.assertFalse(clashes, f"page still shadowing {url}")

    def test_services_menu_is_a_mega_menu(self):
        Menu = self.env['website.menu']
        if 'is_mega_menu' not in Menu._fields:
            self.skipTest("no mega menu support on website.menu")
        _apply_site_structure(self.env)
        for website in self.env['website'].search([]):
            services = Menu.search([
                ('name', '=', 'Services'),
                ('website_id', '=', website.id),
                ('parent_id', '!=', False),
            ])
            self.assertEqual(len(services), 1)
            self.assertTrue(services.is_mega_menu)
            self.assertIn('ab-mega', services.mega_menu_content or '')
            self.assertFalse(services.child_id)

    def test_menus_present_and_idempotent(self):
        Menu = self.env['website.menu']
        _apply_site_structure(self.env)
        counts = {
            (website.id, url): Menu.search_count(
                [('url', '=', url), ('website_id', '=', website.id)])
            for website in self.env['website'].search([])
            for url in ['/about', '/faq', '/booking', '/contactus']
        }
        for key, count in counts.items():
            self.assertGreaterEqual(count, 1, f"menu missing for {key}")
        _apply_site_structure(self.env)
        for (website_id, url), count in counts.items():
            self.assertEqual(
                Menu.search_count(
                    [('url', '=', url), ('website_id', '=', website_id)]),
                count, f"menu for {url} duplicated on re-run")

    def test_every_menu_entry_points_at_a_page_that_exists(self):
        """A menu entry whose page is missing is a 404 the visitor finds.

        This is the shape the live site was found in: the nav bar rendered
        Home / Services / About us / FAQ / Book a visit and every one of
        them 404'd, because the menus are created in Python while the pages
        are XML records that went away with the module.
        """
        shipped = {url for _xmlid, url in PAGES}
        for name, url, _sequence, children in SITE_MENUS:
            for entry_name, entry_url in [(name, url)] + [
                    (c_name, c_url) for c_name, c_url, _c_seq in children]:
                if entry_url in KEEP_PUBLISHED_URLS:
                    continue  # native page, not ours to ship
                self.assertIn(
                    entry_url, shipped,
                    "menu %r points at %s, which this module does not ship - "
                    "visitors would get a 404" % (entry_name, entry_url))

    def test_uninstall_hook_covers_every_menu_it_builds(self):
        """Whatever the menu builds, the uninstall hook must take away.

        Without this the module leaves a full navigation bar behind on
        uninstall, every link of it dead.
        """
        owned = _owned_menu_urls()
        for name, url, _sequence, children in SITE_MENUS:
            for entry_url in [url] + [c_url for _c, c_url, _s in children]:
                if entry_url in KEEP_PUBLISHED_URLS:
                    self.assertNotIn(
                        entry_url, owned,
                        "%s is a native page and must survive uninstall"
                        % entry_url)
                else:
                    self.assertIn(
                        entry_url, owned,
                        "menu %r (%s) would be orphaned on uninstall"
                        % (name, entry_url))
