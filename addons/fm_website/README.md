# fm_website — Aabaan Services public website

The native **Website** app, with Aabaan's pages and brand styling on top.

## What is code, what is configuration

**Code (this module):**

- Four page templates — Home, Services, Compliance, Contact — and the
  `website.page` records that give them URLs.
- One stylesheet on `web.assets_frontend`, scoped entirely under `.fm-site`
  so nothing here can leak into Odoo's own website chrome, the editor or the
  portal.
- A post-init hook that points the website's homepage at `/home` and adds the
  top menu entries. Both are idempotent and neither overrides a choice
  someone already made by hand.

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

## Brand tokens

The stylesheet restates the tokens from
`fm_branding/static/src/scss/_tokens.scss` because the frontend is a separate
asset bundle and cannot see that file. Same palette, two bundles — navy
`#1C2B3A`, orange `#EE7A22`, warm off-white `#FAFAF7`, plus the per-service
colours so a service reads the same on the website and in the cockpit. If a
value changes in `fm_branding`, change it here too.
