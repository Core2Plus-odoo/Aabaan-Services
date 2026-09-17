"""The site has to be there and it has to be true.

Two things these tests protect. First, that every page still resolves to a
published URL after an upgrade — the `website.page` records are noupdate, so
a renamed template would silently leave a dead menu entry pointing nowhere.
Second, that the LocalBusiness JSON-LD is valid JSON and cannot break out of
its <script> tag, because it is assembled from a company name that a user
can type anything into.
"""
import json

from odoo.tests import TransactionCase, tagged

from ..hooks import TOP_MENU, _post_init_website

# (xml id, url) — every page the module ships.
EXPECTED_PAGES = [
    ('fm_website.page_home', '/home'),
    ('fm_website.page_services', '/services'),
    ('fm_website.page_compliance', '/compliance'),
    ('fm_website.page_about', '/about'),
    ('fm_website.page_contact', '/contact-us'),
]


@tagged('fm', 'fm_website', 'post_install', '-at_install')
class TestWebsitePages(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([], limit=1)

    # -- pages ---------------------------------------------------------
    def test_every_page_is_published_at_its_url(self):
        for xml_id, url in EXPECTED_PAGES:
            with self.subTest(page=xml_id):
                page = self.env.ref(xml_id, raise_if_not_found=False)
                self.assertTrue(page, "%s did not load" % xml_id)
                self.assertEqual(page.url, url)
                self.assertTrue(page.is_published,
                                "%s should ship published" % xml_id)
                self.assertEqual(page.view_id.type, 'qweb')

    def test_every_menu_entry_points_at_a_shipped_page(self):
        """A menu entry whose URL no page serves is a 404 in the navbar."""
        page_urls = {url for _xml_id, url in EXPECTED_PAGES}
        for url, label, _sequence in TOP_MENU:
            with self.subTest(menu=label):
                self.assertIn(url, page_urls,
                              "top menu offers %s but no page serves it" % url)

    def test_shared_blocks_exist(self):
        """The pages t-call these; a rename would break the render."""
        for xml_id in ('fm_website.compliance_strip',
                       'fm_website.contact_band'):
            with self.subTest(template=xml_id):
                self.assertTrue(self.env.ref(xml_id, raise_if_not_found=False),
                                "%s is t-called by the pages" % xml_id)

    # -- structured data ----------------------------------------------
    def test_jsonld_is_valid_json_and_names_the_company(self):
        raw = self.website._fm_localbusiness_jsonld()
        self.assertTrue(raw, "expected structured data for a named company")
        data = json.loads(raw)
        self.assertEqual(data['@type'], 'LocalBusiness')
        company = self.website.company_id or self.env.company
        self.assertEqual(data['name'], company.name)
        self.assertTrue(data.get('url'))

    def test_jsonld_cannot_escape_its_script_tag(self):
        """A company name is free text. It must not be able to close the
        <script> or inject markup."""
        company = self.website.company_id or self.env.company
        company.name = 'Aabaan </script><img src=x> & Co'
        raw = self.website._fm_localbusiness_jsonld()
        self.assertNotIn('<', raw)
        self.assertNotIn('>', raw)
        self.assertNotIn('&', raw)
        # Still valid JSON, and the name survives once decoded.
        self.assertEqual(json.loads(raw)['name'], 'Aabaan </script><img src=x> & Co')

    def test_jsonld_survives_a_broken_source(self):
        """A page must render even if the structured data cannot be built."""
        website = self.website

        def boom(*args, **kwargs):
            raise ValueError('no company today')

        self.patch(type(website), '_fm_build_localbusiness_jsonld', boom)
        self.assertEqual(website._fm_localbusiness_jsonld(), '')

    def test_areas_served_follow_the_branches_when_fm_branch_is_installed(self):
        Branch = self.env.get('fm.branch')
        if Branch is None:
            self.skipTest('fm_branch is not installed on this database')
        cities = [b.city for b in Branch.sudo().search([], order='id') if b.city]
        if not cities:
            self.skipTest('no branch carries a city on this database')
        data = json.loads(self.website._fm_localbusiness_jsonld())
        self.assertEqual(data.get('areaServed'), list(dict.fromkeys(cities)))

    # -- crawler rules -------------------------------------------------
    def test_robots_keeps_the_native_sitemap_and_adds_our_rules(self):
        """Appended, never replaced — losing Odoo's Sitemap line at launch
        would cost more than the Disallow rules gain."""
        tmpl = self.env.ref('fm_website.robots')
        arch = tmpl.arch_db or ''
        self.assertIn('Disallow: /web', arch)
        self.assertIn('Disallow: /website/info', arch)
        self.assertEqual(tmpl.inherit_id, self.env.ref('website.robots'))

    # -- the install hook ----------------------------------------------
    def test_menu_hook_is_idempotent(self):
        """Upgrading must not stack up a second copy of every menu entry."""
        Menu = self.env['website.menu']
        urls = [url for url, _label, _seq in TOP_MENU]

        _post_init_website(self.env)
        before = {url: Menu.search_count([('url', '=', url)]) for url in urls}
        _post_init_website(self.env)
        after = {url: Menu.search_count([('url', '=', url)]) for url in urls}

        self.assertEqual(before, after,
                         "running the post-init hook twice duplicated menus")

    def test_homepage_choice_is_never_overridden(self):
        """Someone who picked a homepage by hand keeps it."""
        other = self.env.ref('fm_website.page_services')
        self.website.homepage_id = other.id
        _post_init_website(self.env)
        self.assertEqual(self.website.homepage_id, other,
                         "the hook overrode a homepage chosen by hand")
