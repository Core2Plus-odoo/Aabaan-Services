import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Switch the FM auto-schedule cron off on databases that already have it.

    data/cron.xml is noupdate="1", so shipping the record with active=False
    fixes new installs and does nothing at all for existing ones — the cron
    would keep running unattended on exactly the databases that matter.

    Why it goes off: two generators write project.task visits on this
    platform — fm.contract._generate_schedule() behind this cron, and
    sale.order._generate_visit_schedule() in aabaan_visit_schedule. A
    customer reachable from both sides gets two sets of visits, silently.
    The platform is consolidating onto the sale order, so that generator is
    the one that stays.

    Only the cron is touched. _cron_auto_schedule() and the manual "Generate
    Visits" button are left intact, so nothing that a person deliberately
    clicks changes behaviour today — this closes the unattended path only.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref("fm_fsm.cron_fm_fsm_auto_schedule", raise_if_not_found=False)
    if not cron:
        _logger.info("FM FSM: no auto-schedule cron on this database.")
        return
    if not cron.active:
        _logger.info("FM FSM: auto-schedule cron already inactive.")
        return
    cron.active = False
    _logger.warning(
        "FM FSM: auto-schedule cron switched OFF. It generated project.task "
        "visits from fm.contract, duplicating the visits "
        "sale.order._generate_visit_schedule() creates from the sale order. "
        "The sale order is now the single source of visits. Re-enable under "
        "Settings > Technical > Scheduled Actions only if that changes.")
