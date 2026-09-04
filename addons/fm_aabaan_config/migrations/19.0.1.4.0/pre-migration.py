import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """The fourth branch is Fujairah, not Abu Dhabi.

    The seed shipped Abu Dhabi; the business operates Fujairah. Correcting
    the data file alone would not fix an installed database twice over: the
    file is ``noupdate="1"`` so the existing record is never rewritten, and
    the new xmlid would create a *second* branch beside the wrong one.

    So convert the record in place, keeping its id. Anything already
    pointing at it — contracts, work orders, employees, invoices — follows
    the rename instead of being orphaned against a branch nobody uses. This
    runs before the data file loads, so by the time Odoo reads
    ``branch_fujairah`` the anchor already exists and noupdate leaves it be.

    Idempotent: a database that has already been converted, or one that
    never had the Abu Dhabi seed, is left alone.
    """
    cr.execute("""
        SELECT res_id FROM ir_model_data
         WHERE module = 'fm_aabaan_config'
           AND name = 'branch_abu_dhabi'
           AND model = 'fm.branch'
    """)
    row = cr.fetchone()
    if not row:
        _logger.info("Aabaan config: no Abu Dhabi branch anchor — nothing to "
                     "convert.")
        return

    cr.execute("""
        SELECT 1 FROM ir_model_data
         WHERE module = 'fm_aabaan_config' AND name = 'branch_fujairah'
    """)
    if cr.fetchone():
        _logger.warning(
            "Aabaan config: both branch_abu_dhabi and branch_fujairah "
            "anchors exist. Leaving both alone — merge them by hand so no "
            "contract or work order loses its branch.")
        return

    branch_id = row[0]
    cr.execute("""
        UPDATE ir_model_data SET name = 'branch_fujairah'
         WHERE module = 'fm_aabaan_config'
           AND name = 'branch_abu_dhabi'
           AND model = 'fm.branch'
    """)
    cr.execute("""
        UPDATE fm_branch
           SET name = 'Aabaan Services — Fujairah',
               code = 'FUJ',
               emirate = 'fujairah',
               city = 'Fujairah'
         WHERE id = %s
    """, (branch_id,))
    _logger.info(
        "Aabaan config: branch %s converted from Abu Dhabi to Fujairah; "
        "everything already linked to it follows.", branch_id)
