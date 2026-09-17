"""Structured data for the public site.

The only Python on the website side. It exists because a Schema.org
LocalBusiness block has to be *true* — name, phone, address and the
emirates we actually cover — and the truth lives in records, not in a
template someone has to remember to edit.

Nothing here may raise during a page render: a search engine losing its
structured data is a bad day, a 500 on the homepage is a worse one.
"""
import json
import logging

from markupsafe import Markup

from odoo import models

_logger = logging.getLogger(__name__)

# `<`, `>` and `&` never appear in JSON *syntax* — only inside string values —
# so escaping them across the whole dump is safe, keeps the JSON valid, and
# stops a company name containing "</script>" from breaking out of the tag.
_SCRIPT_SAFE = {'<': '\\u003c', '>': '\\u003e', '&': '\\u0026'}


class Website(models.Model):
    _inherit = 'website'

    def _fm_localbusiness_jsonld(self):
        """Return the site's LocalBusiness JSON-LD, ready to drop in a
        <script>, or '' when there is nothing truthful to say.

        Sources, in order of preference, all of them records:
          * the website's company           -> name, phone, email, address
          * ``fm.branch``, when installed   -> the emirates served, and the
                                               branch phone numbers
        Returns '' rather than a partial block if the company is missing,
        because a LocalBusiness without a name is worse than none.
        """
        self.ensure_one()
        try:
            payload = self._fm_build_localbusiness_jsonld()
        except Exception:  # pragma: no cover - a page must still render
            _logger.warning(
                "fm_website: could not build LocalBusiness JSON-LD for %s.",
                self.display_name, exc_info=True)
            return ''
        if not payload:
            return ''
        for char, escape in _SCRIPT_SAFE.items():
            payload = payload.replace(char, escape)
        # Markup so QWeb emits the JSON as-is; the escaping above is what
        # makes that safe.
        return Markup(payload)

    def _fm_build_localbusiness_jsonld(self):
        company = self.company_id or self.env.company
        if not company or not company.name:
            return ''

        data = {
            '@context': 'https://schema.org',
            '@type': 'LocalBusiness',
            'name': company.name,
            'url': self.domain or self.get_base_url(),
        }

        phones = self._fm_phone_numbers(company)
        if phones:
            data['telephone'] = phones
        if company.email:
            data['email'] = company.email

        address = self._fm_postal_address(company.partner_id)
        if address:
            data['address'] = address

        areas = self._fm_areas_served(company)
        if areas:
            data['areaServed'] = areas

        return json.dumps(data, indent=2, ensure_ascii=False)

    def _fm_phone_numbers(self, company):
        """Company phone first, then any distinct branch numbers."""
        numbers = []
        for number in [company.phone, company.mobile if 'mobile' in company._fields else None]:
            number = (number or '').strip()
            if number and number not in numbers:
                numbers.append(number)
        for branch in self._fm_branches():
            number = (branch.phone or '').strip()
            if number and number not in numbers:
                numbers.append(number)
        return numbers

    @staticmethod
    def _fm_postal_address(partner):
        if not partner:
            return None
        address = {'@type': 'PostalAddress'}
        for key, value in (
            ('streetAddress', ', '.join(
                part for part in (partner.street, partner.street2) if part)),
            ('addressLocality', partner.city),
            ('addressRegion', partner.state_id.name if partner.state_id else ''),
            ('postalCode', partner.zip),
            ('addressCountry', partner.country_id.code if partner.country_id else ''),
        ):
            value = (value or '').strip()
            if value:
                address[key] = value
        # Only worth emitting if it says where the place actually is.
        return address if address.get('addressLocality') else None

    def _fm_areas_served(self, company):
        """The emirates we cover, from fm.branch; the company city otherwise."""
        cities = [branch.city for branch in self._fm_branches() if branch.city]
        if not cities:
            city = company.partner_id.city if company.partner_id else None
            cities = [city] if city else []
        # dict.fromkeys keeps first-seen order while dropping duplicates.
        return list(dict.fromkeys(cities))

    def _fm_branches(self):
        """Active branches, or an empty recordset when fm_branch is absent.

        fm_website deliberately does not depend on fm_branch — the site has
        to install on a plain Website + fm_branding database. When the FM
        suite is there, the emirates come from it instead of from a list
        kept by hand.
        """
        Branch = self.env.get('fm.branch')
        if Branch is None:
            return ()
        return Branch.sudo().search([], order='id')
