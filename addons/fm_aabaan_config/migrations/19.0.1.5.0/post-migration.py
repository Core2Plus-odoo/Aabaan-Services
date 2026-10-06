import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# The five agreement templates the seed used to ship. They were Aaban's
# wording re-written; they are replaced by Aaban's own contract documents,
# one template per document (data/fm_contract_agreement_template_data.xml).
RETIRED = (
    "agreement_template_water_tank",
    "agreement_template_termite",
    "agreement_template_cleaning_deep",
    "agreement_template_pest_dubai",
    "agreement_template_pest_standard",
)


def migrate(cr, version):
    """Remove the five retired agreement templates.

    Taking them out of the data file is not enough: the file is
    ``noupdate="1"``, and an upgrade never deletes a noupdate record that
    has left its file. Their lines go with them (``ondelete="cascade"``).

    A contract that used one keeps its own copy of the wording (its
    agreement lines are copies, not links); only its link to the retired
    template is cleared.

    Idempotent: a database without them is left alone.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    for name in RETIRED:
        template = env.ref("fm_aabaan_config.%s" % name, raise_if_not_found=False)
        if template:
            _logger.info("fm_aabaan_config: removing retired agreement template %s", template.display_name)
            template.with_context(active_test=False).unlink()
