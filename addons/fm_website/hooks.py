import logging

_logger = logging.getLogger(__name__)

# (url, label, sequence) for the top menu. Home is the site root, so it is
# not listed — Odoo's own "Home" entry already points there.
TOP_MENU = [
    ('/services', 'Services', 20),
    ('/compliance', 'Compliance', 30),
    ('/contact-us', 'Contact', 40),
]


def _post_init_website(env):
    """Point the website at our homepage and add the top menu entries.

    Both steps are best-effort and idempotent. A website whose homepage is
    already set by hand is left alone, and a menu entry that already exists
    for a URL is not duplicated — reinstalling or upgrading must not stack
    up menu items.
    """
    _set_homepage(env)
    _add_menu_entries(env)


def _set_homepage(env):
    page = env.ref('fm_website.page_home', raise_if_not_found=False)
    if not page:
        return
    Website = env['website'].sudo()
    if 'homepage_id' not in Website._fields:
        _logger.info(
            "Aabaan website: this build has no website.homepage_id — set the "
            "homepage by hand under Website > Configuration.")
        return
    for website in Website.search([]):
        if website.homepage_id:
            continue  # someone already chose one; never override that
        website.homepage_id = page.id
        _logger.info("Aabaan website: homepage of %s set to /home.",
                     website.name)


def _add_menu_entries(env):
    Menu = env['website.menu'].sudo()
    for website in env['website'].sudo().search([]):
        root = Menu.search(
            [('parent_id', '=', False), ('website_id', '=', website.id)],
            limit=1)
        if not root:
            _logger.info(
                "Aabaan website: %s has no root menu yet — add the pages "
                "under Website > Site > Menu.", website.name)
            continue
        for url, label, sequence in TOP_MENU:
            existing = Menu.search([
                ('website_id', '=', website.id), ('url', '=', url)], limit=1)
            if existing:
                continue
            Menu.create({
                'name': label,
                'url': url,
                'parent_id': root.id,
                'sequence': sequence,
                'website_id': website.id,
            })
            _logger.info("Aabaan website: added menu entry %s -> %s on %s.",
                         label, url, website.name)
