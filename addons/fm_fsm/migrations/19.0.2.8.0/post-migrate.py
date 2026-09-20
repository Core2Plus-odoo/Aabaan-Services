import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Stage xmlid -> (sequence, requires a service document)
STAGE_STATE = [
    ("fm_fsm.fsm_stage_completed", 6, True),
    ("fm_fsm.fsm_stage_signed_off", 7, True),
    ("fm_fsm.fsm_stage_cancelled", 8, False),
]


def migrate(cr, version):
    """Make room for Pending Documents and flag the closing stages.

    data/fsm_stages.xml is noupdate="1": the new Pending Documents record is
    created on upgrade, but the stages that already exist are left exactly as
    they were. Without this, an existing database would get the new stage at
    sequence 5 tied with Completed -- ordering then falls to the id, so
    Pending Documents would sort *after* Completed, which reads backwards on
    the kanban -- and neither closing stage would require a document, so the
    whole gate would quietly do nothing on precisely the databases that have
    real visits in them.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, sequence, requires_document in STAGE_STATE:
        stage = env.ref(xmlid, raise_if_not_found=False)
        if not stage:
            _logger.warning("fm_fsm: %s not found; stage order left alone.", xmlid)
            continue
        stage.write({
            "sequence": sequence,
            "fm_requires_document": requires_document,
        })
    _logger.info(
        "fm_fsm: Pending Documents inserted; Completed and Signed Off now "
        "require a service document.")
