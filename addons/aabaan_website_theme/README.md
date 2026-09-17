> **This module lives in two repos.** It is maintained in the `aabaan`
> repo and ported verbatim here, because each Odoo.sh project loads only
> its own addons path: with the source only in `aabaan`, this instance
> logged `manifest not found` / `not installable, skipped` and jammed the
> module-operation lock. The technical name is deliberately unchanged so
> the existing `ir_module_module` row resolves instead of orphaning.
> Nothing in it is repo-specific — it depends only on `website` and
> `website_crm` and references only its own xmlids — so the two copies can
> stay identical. Change it in `aabaan` first, then copy across.

# Aabaan Website Theme

Code-defined, booking-first website for Aaban Classic Building Cleaning
L.L.C., in the approved Urban Company / Justlife style.

## What is code (this module)

| Piece | Where |
|---|---|
| Homepage at `/` (hero, chips, trust bar, service tiles, 3 steps, AMC + coverage) | `views/home_page.xml` |
| `/services` overview | `views/services_index.xml` |
| `/services/pest-control`, `/services/water-tank`, `/services/anti-termite`, `/services/deep-cleaning` | `views/service_pages.xml` |
| `/about` (licence, approvals, numbers from the contract master sheet), `/faq` | `views/about_page.xml`, `views/faq_page.xml` |
| `/booking` (branded visit-request form → CRM lead) + `/booking-thanks` | `views/booking_page.xml` |
| `/contactus` beautification (branded hero + contact tiles over the native form) | `views/contact_page.xml` |
| Site-wide footer (replaces `website.footer_custom`) + fixed mobile action bar | `views/layout.xml` |
| 301 redirect `/home-v2 → /` (`website.rewrite`) | `views/layout.xml` |
| All styling — brand ink `#17171a`, orange `#ef7d25`, navbar, buttons | `static/src/scss/aabaan_theme.scss` |
| Homepage switch-over + menu build (idempotent, shared by install hook and migration) | `__init__.py` |

The switch-over parks any previous page at `/` to `/home-classic`
(unpublished, never deleted), clears `website.homepage_url`, and makes each
website's main menu exactly: Home, Services (dropdown), About us, FAQ,
Contact, Book a visit. Services renders as a native **full-width mega
menu** — service tiles with rate-card prices, trust chips and a dark AMC
rail with the contact CTA; its content is re-applied on every upgrade, so
edit it in `MEGA_MENU_HTML` (`__init__.py`), not in the builder. Legacy
internal menu items are removed (external http/mailto/tel links are
kept), and every legacy page is unpublished —
except the keep-list (`/booking`, `/contactus`, legal pages). Old pages
stay in the website page manager and can be republished with one click.

## Native Odoo views this site switches

Two things the stock site shows that this one should not. Both are handled
by flipping views Odoo's own builder toggles -- not by overriding
templates -- in `NATIVE_VIEW_STATE` (`__init__.py`):

| View | Set to | Why |
|---|---|---|
| `website.footer_no_copyright` | active | The branded footer already carries the copyright. Odoo's copyright bar duplicated it *and* still showed the stock placeholder `Copyright (c) Company name`. |
| `website.header_call_to_action` | inactive | It renders a `Contact Us` button to `/contactus`, competing with `Book a visit` (the primary CTA) and the `Contact` menu entry. |

Each is resolved with `raise_if_not_found=False`: if a future Odoo renames
or drops one, the hook logs and moves on. It runs on every install and
migration, so a hard reference would fail the install and take the registry
with it -- the cost of losing a footer tweak is not worth that.

## Uninstalling

The pages are XML records and go with the module. The menus are **not** —
`_rebuild_menu` creates them directly, with no `ir.model.data` anchor — so
the `uninstall_hook` removes them explicitly. Without it, uninstalling left
the site showing the full navigation bar (Home, Services, About us, FAQ,
Book a visit) with every link 404ing, which is exactly how the live site
was found. `/contactus` and genuinely external links (`http`, `mailto`,
`tel`) are left alone.

If you ever see that nav-intact / pages-gone state again, the fix is to
install or upgrade this module: the page records are not `noupdate`, so an
upgrade recreates all ten of them, published, and rebuilds the menu.

## What is configuration (native Odoo, not this module)

- The contact page is the native `/contactus` form (`website_crm`) — leads
  land in CRM as before.
- All pages stay editable in the website builder afterwards.
- If the live website had a builder-customised footer, that website-specific
  copy can shadow the branded footer — reset the footer template in the
  builder to pick this one up.
- Facts on `/about` come from the trade licence and the contract master
  sheet (600+ contracts, 4,500+ visits/year); update them there when the
  business numbers move.
