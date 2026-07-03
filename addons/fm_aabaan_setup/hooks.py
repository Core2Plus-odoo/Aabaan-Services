# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def _post_init_apply(env):
    """Apply safe, non-destructive base settings for UAE companies.

    Deliberately avoids anything that could disturb live accounting or payroll:
    it only sets the country (if unset) and the default working calendar (if the
    company still uses the generic Odoo week). Currency and accounting are left
    to the runbook.
    """
    ae = env.ref("base.ae", raise_if_not_found=False)
    uae_cal = env.ref("fm_aabaan_setup.resource_calendar_uae", raise_if_not_found=False)

    for company in env["res.company"].search([]):
        # Country -> UAE if not already set.
        if ae and not company.country_id:
            company.country_id = ae.id

        # Default working calendar -> UAE Mon–Fri, only if the company is still on
        # the stock 'Standard 40 hours/week' calendar (don't override a custom one).
        cal = company.resource_calendar_id
        if uae_cal and (not cal or (cal.name or "").lower().startswith("standard")):
            company.resource_calendar_id = uae_cal.id
            _logger.info("Aabaan setup: set UAE working calendar on %s", company.name)
