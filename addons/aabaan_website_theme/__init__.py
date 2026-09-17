import logging

_logger = logging.getLogger(__name__)

# Site structure: top menu entries (name, url, sequence, children).
SITE_MENUS = [
    ('Home', '/', 10, []),
    ('Services', '/services', 20, [
        ('All services', '/services', 1),
        ('Pest Control', '/services/pest-control', 2),
        ('Water Tank Cleaning', '/services/water-tank', 3),
        ('Anti-Termite', '/services/anti-termite', 4),
        ('Deep Cleaning', '/services/deep-cleaning', 5),
    ]),
    ('About us', '/about', 30, []),
    ('FAQ', '/faq', 40, []),
    ('Contact', '/contactus', 50, []),
    ('Book a visit', '/booking', 60, []),
]

# Full-width mega menu for the Services entry (native website.menu
# mega-menu). Classes come from the theme SCSS asset; the content is
# re-applied on every upgrade so it stays in sync with the pages.
MEGA_MENU_HTML = """
<div class="ab-mega">
  <div class="container">
    <div class="row g-4">
      <div class="col-lg-8">
        <span class="ab-kick">What we do</span>
        <div class="row g-2">
          <div class="col-sm-6">
            <a href="/services/pest-control" class="ab-mega-item">
              <span class="ic">🪳</span>
              <span class="tx"><b>Pest Control — Home</b>
              <small>Cockroaches, bed bugs, rodents · from AED 200/visit</small></span>
            </a>
          </div>
          <div class="col-sm-6">
            <a href="/services/pest-control" class="ab-mega-item">
              <span class="ic">🏢</span>
              <span class="tx"><b>Pest Control — Business</b>
              <small>F&amp;B AMCs · Dubai LO 11 compliant · 2 visits/month</small></span>
            </a>
          </div>
          <div class="col-sm-6">
            <a href="/services/water-tank" class="ab-mega-item">
              <span class="ic">💧</span>
              <span class="tx"><b>Water Tank Cleaning</b>
              <small>From AED 0.35/gallon · certificate issued</small></span>
            </a>
          </div>
          <div class="col-sm-6">
            <a href="/services/anti-termite" class="ab-mega-item">
              <span class="ic">🐜</span>
              <span class="tx"><b>Anti-Termite Treatment</b>
              <small>AED 14.50–18/m² · 10-year written warranty</small></span>
            </a>
          </div>
          <div class="col-sm-6">
            <a href="/services/deep-cleaning" class="ab-mega-item">
              <span class="ic">🧽</span>
              <span class="tx"><b>Deep Cleaning</b>
              <small>Move-in / move-out · fixed price up front</small></span>
            </a>
          </div>
          <div class="col-sm-6">
            <a href="tel:80022226" class="ab-mega-item">
              <span class="ic">🚨</span>
              <span class="tx"><b>Emergency Call-out</b>
              <small>Same-day Dubai · 24–48h other emirates</small></span>
            </a>
          </div>
        </div>
        <div class="ab-mega-foot">
          <a href="/services" class="ab-mega-all">All services →</a>
          <span class="ab-mega-chip">✓ Municipality approved</span>
          <span class="ab-mega-chip">✓ MOCCAE pesticides</span>
          <span class="ab-mega-chip">✓ 10-year termite warranty</span>
        </div>
      </div>
      <div class="col-lg-4">
        <div class="ab-mega-rail">
          <span class="ab-kick">Annual contracts</span>
          <b class="d-block mb-1">One contract. Every visit handled.</b>
          <ul>
            <li>Yearly 12 / 4 / 2 visits, scheduled for you</li>
            <li>Free follow-ups every 3 days until clear</li>
            <li>Municipality reporting handled</li>
          </ul>
          <a href="/contactus" class="btn btn-sm ab-btn-book w-100 mb-2">Request an AMC proposal</a>
          <div class="ab-mega-call">
            Call <a href="tel:80022226"><span class="ab-o">800 AABAN</span></a> ·
            <a href="https://wa.me/971558598834">WhatsApp</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
"""

# Pages that must stay published even though this module does not own them:
# the native contact page and common legal pages if the site has them.
# (/booking is module-owned now.)
KEEP_PUBLISHED_URLS = [
    '/contactus', '/contact',
    '/privacy', '/privacy-policy', '/terms', '/terms-of-use', '/legal',
]


def _is_external(menu):
    # '#' is NOT external: dropdown/mega-menu parents carry it, and treating
    # it as external is what let duplicate "Services" items survive cleanup.
    url = menu.url or ''
    return url.startswith(('http://', 'https://', 'mailto:', 'tel:'))


def _rebuild_menu(env, website, root):
    """Wipe-and-rebuild: every internal item under the root is removed and
    the defined set is recreated from scratch. No matching heuristics — the
    end state is identical no matter what history the menu carries. Only
    genuinely external links (http/mailto/tel) survive."""
    Menu = env['website.menu']
    stale = root.child_id.filtered(
        lambda m: (not m.website_id or m.website_id.id == website.id)
        and not _is_external(m))
    if stale:
        stale.unlink()
    mega_ok = ('is_mega_menu' in Menu._fields
               and 'mega_menu_content' in Menu._fields)
    for name, url, sequence, children in SITE_MENUS:
        vals = {'name': name, 'url': url, 'parent_id': root.id,
                'sequence': sequence, 'website_id': website.id}
        if url == '/services' and mega_ok:
            vals.update(is_mega_menu=True, mega_menu_content=MEGA_MENU_HTML)
            Menu.create(vals)
        else:
            parent = Menu.create(vals)
            for c_name, c_url, c_seq in children:
                Menu.create({'name': c_name, 'url': c_url,
                             'parent_id': parent.id, 'sequence': c_seq,
                             'website_id': website.id})


def _module_pages(env):
    data = env['ir.model.data'].search([
        ('module', '=', 'aabaan_website_theme'),
        ('model', '=', 'website.page'),
    ])
    return env['website.page'].browse(data.mapped('res_id')).exists()


def _park_conflicting_pages(env):
    """A website-specific legacy page at the same URL shadows a generic
    module page in Odoo's page routing — visitors would still get the old
    page (or a 404 once it is unpublished). Park every clash out of the
    way: the legacy page moves to <url>-classic, unpublished, recoverable
    from the page manager."""
    Page = env['website.page']
    ours = _module_pages(env)
    for page in ours:
        clashes = Page.search([
            ('url', '=', page.url), ('id', 'not in', ours.ids)])
        if clashes:
            parked = '/home-classic' if page.url == '/' \
                else page.url + '-classic'
            clashes.write({'url': parked, 'is_published': False})


def _retire_legacy_pages(env):
    """Unpublish every website page this module does not own (except the
    keep-list above). Nothing is deleted — the old pages stay in the page
    manager and can be republished with one click."""
    ours = _module_pages(env)
    if not ours:
        # Every page on the site is "not ours" when we own nothing, and the
        # search below would then unpublish the entire website. That state
        # means our own data failed to load, so the safe move is to change
        # nothing and say so.
        _logger.warning(
            "aabaan_website_theme: no module-owned pages found; skipping "
            "legacy retirement rather than unpublishing the whole site.")
        return
    legacy = env['website.page'].search([
        ('id', 'not in', ours.ids),
        ('url', 'not in', KEEP_PUBLISHED_URLS),
        ('is_published', '=', True),
    ])
    if legacy:
        legacy.write({'is_published': False})


def _apply_site_structure(env):
    """Idempotent switch-over shared by the install hook and the upgrade
    migrations. The overhauled site fully replaces the old one:

    - the booking-first page is served at `/` (any previous homepage is
      parked, unpublished, at /home-classic — recoverable, never deleted);
    - the homepage pointer is cleared;
    - the top menu is wiped and rebuilt to exactly the defined set — only
      genuinely external links (http/mailto/tel) survive, so no history of
      duplicates or old dropdowns can persist;
    - legacy pages clashing with a module page URL are parked at
      <url>-classic (they would shadow the module page in routing);
    - every other legacy page is unpublished (see _retire_legacy_pages)."""
    Menu = env['website.menu']
    Website = env['website']

    home = env.ref('aabaan_website_theme.page_home_v2', raise_if_not_found=False)
    if home and home.url != '/':
        home.write({'url': '/'})
    _park_conflicting_pages(env)
    if 'homepage_url' in Website._fields:
        Website.search([]).write({'homepage_url': False})

    for website in Website.search([]):
        root = Menu.search([('parent_id', '=', False),
                            ('website_id', '=', website.id)], limit=1)
        if not root:
            root = env.ref('website.main_menu', raise_if_not_found=False)
        if not root:
            continue
        _rebuild_menu(env, website, root)

    _retire_legacy_pages(env)


def _post_init_hook(env):
    _apply_site_structure(env)


def _owned_menu_urls():
    """The menu URLs this module owns — every entry it builds except
    /contactus, whose page is native and outlives this module."""
    urls = set()
    for _name, url, _sequence, children in SITE_MENUS:
        urls.add(url)
        for _c_name, c_url, _c_seq in children:
            urls.add(c_url)
    return urls - set(KEEP_PUBLISHED_URLS)


def _uninstall_hook(env):
    """Take the menu bar down with the module.

    The pages are XML records, so uninstalling drops them along with their
    ir.model.data anchors. The menus are not: _rebuild_menu creates them
    directly with Menu.create() and no xmlid, so without this hook they
    survive uninstall and the site is left advertising a full navigation
    bar in which every link 404s — nav intact, every page gone.

    Only menus pointing at pages this module owns are removed; genuinely
    external links and /contactus are left alone.
    """
    Menu = env['website.menu']
    orphans = Menu.search([('url', 'in', list(_owned_menu_urls()))]).filtered(
        lambda m: not _is_external(m))
    if orphans:
        _logger.info("aabaan_website_theme: removing %s menu entries whose "
                     "pages go with the module.", len(orphans))
        orphans.unlink()
