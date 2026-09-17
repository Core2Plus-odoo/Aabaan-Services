# fm_website — Aabaan Services public website

The native **Website** app, with Aabaan's pages and brand styling on top.

## What is code, what is configuration

**Code (this module):**

- Five page templates — Home, Services, Compliance, About, Contact — and
  the `website.page` records that give them URLs.
- One stylesheet on `web.assets_frontend`, scoped entirely under `.fm-site`
  so nothing here can leak into Odoo's own website chrome, the editor or the
  portal.
- A post-init hook that points the website's homepage at `/home` and adds the
  top menu entries. Both are idempotent and neither overrides a choice
  someone already made by hand.
- Schema.org **LocalBusiness** structured data, built from the company
  record and — when the FM suite is installed — from `fm.branch`, so the
  emirates in the markup are the emirates in the database.
- Two `robots.txt` rules **appended** to Odoo's own.

**Configuration (done in Odoo, not here):**

- **Logo, favicon, social image** — Website → Configuration → Website.
- **Web fonts.** The stylesheet asks for Instrument Serif and Inter and falls
  back to Georgia and the system sans. Add the real fonts under Website →
  Configuration → Website → Fonts; that is the standard-first route and needs
  no code.
- **Contact form.** Deliberately not shipped. Drop Odoo's own *Form* snippet
  onto the Contact page in the editor once CRM is configured, and it posts
  straight to `crm.lead`. A hand-rolled form here would be a second, worse
  pipeline.
- **Photography.** The design is typographic and works with no images at all,
  so the site can go live before a shoot. Add photos through the editor's
  image blocks in the `oe_structure` zones at the top and bottom of each page.
- **SEO** — title, description and social preview per page, in the editor.

## Editing the pages

Every page is an ordinary `website.page`. Staff open it, click text and type;
Odoo saves the edit back into the view. The `oe_structure` zones at the top
and bottom of each page accept dragged-in snippets. None of that requires
this module to change.

The one thing to know: the `website.page` records are `noupdate="1"`, so an
upgrade never un-publishes a page or resets a URL someone changed. The
templates themselves stay updatable, which is what lets us ship design fixes
without clobbering content edits.

## Why the site leads with compliance

In UAE facility management the differentiator is documented compliance, not
adjectives — an inspector, an owners association or an insurer asks for the
certificate, not the invoice. So the credentials strip sits directly under
the hero, and Compliance is a top-level page rather than a paragraph in an
About page.

## No invented numbers

There is no "years of experience" counter, no "customers served", no
satisfaction percentage. Every claim on the site traces to something in this
repository or to the licences (Rule 4):

| Claim on the site | Source |
|---|---|
| Four emirates, local teams | `fm_aabaan_config/data/fm_branch_data.xml` |
| The seven service lines | `fm_aabaan_config/data/product_data.xml` |
| Dubai Municipality pest control permit | `fm_compliance_regime_data.xml` |
| Civil Defence fire &amp; life-safety inspection | `fm_compliance_regime_data.xml` |
| Water tank cleaning &amp; disinfection certificate | `fm_compliance_regime_data.xml` |
| Local Order No. 11 of 2003 | `fm_contract_agreement_template_data.xml` |
| Dubai branch address and phone | `fm_branch_data.xml` |
| 800 AABAN, mobiles, email | Brand contacts in `CLAUDE.md` |
| One trade licence per emirate | The licence documents (Ajman, Dubai, Sharjah) |

Sharjah, Ajman and Fujairah show as offices without street addresses because
none are recorded in the repo. Fill them in on the Contact page in the editor
when you have them — that is a content edit, not a code change.

## Structured data and robots.txt

`website._fm_localbusiness_jsonld()` assembles the LocalBusiness block from
records, never from a list kept by hand: name, phone, email and address come
from the website's company, and `areaServed` plus the branch phone numbers
come from `fm.branch` when it is installed. The module does **not** depend on
`fm_branch` — the site installs on plain Website + `fm_branding`, and simply
says less.

Two rules the code follows, both tested:

- It returns `''` rather than a half-true block. A LocalBusiness with no name
  is worse than no LocalBusiness, and a page must render even when the
  structured data cannot be built.
- `<`, `>` and `&` are escaped as `\uXXXX` across the whole dump. They never
  appear in JSON *syntax*, only inside string values, so this keeps the JSON
  valid while stopping a company name containing `</script>` from breaking
  out of the tag.

`robots.txt` is **inherited and appended**, never replaced. Odoo's own
template already emits the `Sitemap:` line pointing at this website's real
domain; losing that at launch would cost far more than the two `Disallow`
rules gain. The sitemap itself is native — nothing to configure.

## Launch checklist

Everything below is configuration in Odoo, not code here. The site renders
without any of it; these are the things that make it a launch rather than a
deploy.

| | Where |
|---|---|
| Logo, favicon, social share image | Website → Configuration → Website |
| Real web fonts (Instrument Serif, Inter) | Website → Configuration → Website → Fonts |
| Per-page title, description, social preview | The page editor, Promote → Optimize SEO |
| Contact form → `crm.lead` | Drop Odoo's *Form* snippet on the Contact page |
| Photography in the `oe_structure` zones | The page editor |
| Blog | Install `website_blog`; no code needed here |
| Domain and SSL | Odoo.sh → Settings → Domains |
| Google Search Console + sitemap submission | `/sitemap.xml` is served natively |

**Not shipped, and deliberately: a privacy policy and terms of use.** The
contact form collects personal data, so the site should not go live in the UAE
without them — but they are legal texts that have to be written and approved by
the business, not generated here. Add them as ordinary pages in the editor.

## What was merged in from `aaban_website_booking`

That module (in the `aabn-services` repo) was the second website for the same
company — 9 pages, a `/booking` controller, SEO and tests. It could never run
here: separate repo, separate addons path, and it depends on `aaban_studio`,
`aaban_branding` and `aaban_service_catalog`, none of which exist in this
build.

Taken: the SEO layer (structured data, robots rules) and the idea of testing
that the pages are actually there.

Not taken, with reasons:

- **The `/booking` controller.** Booking was not in scope for this pass, and
  the controller writes `x_aaban_*` manual fields on `crm.lead` that only
  exist on the other database. When booking is wanted here, the standard-first
  route is Odoo's own *Form* snippet posting to `crm.lead` — no controller.
- **Its `website.menu` XML records.** They attach by searching for
  `/default-main-menu`, which silently creates nothing if that URL was
  renamed. The post-init hook here is idempotent and logs when it cannot find
  a root menu.
- **Its hardcoded `aabanservices.com` and phone list.** The same numbers are
  already records in `fm_aabaan_config`; the JSON-LD reads them from there, so
  they cannot drift.
- **Cleaning and Pest Control as separate pages.** The Services page already
  covers both in depth. Splitting them is an SEO choice worth making later
  with real copy, not by cutting the existing page in half.

## Brand tokens

The stylesheet restates the tokens from
`fm_branding/static/src/scss/_tokens.scss` because the frontend is a separate
asset bundle and cannot see that file. Same palette, two bundles — navy
`#1C2B3A`, orange `#EE7A22`, warm off-white `#FAFAF7`, plus the per-service
colours so a service reads the same on the website and in the cockpit. If a
value changes in `fm_branding`, change it here too.
