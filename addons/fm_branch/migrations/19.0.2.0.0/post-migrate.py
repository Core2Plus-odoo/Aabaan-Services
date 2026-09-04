import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Carry branch_id from fm_contract onto its sale_order.

    branch_id used to be defined on fm.contract, which gave that model its
    own column. It now lives on sale.order and reaches fm.contract through
    the _inherits delegation, so the ORM reads sale_order.branch_id and the
    old column is no longer consulted. Without this step every contract
    would appear to have lost its branch.

    The old column is left in place rather than dropped: the data is copied,
    not moved, so this is reversible if anything looks wrong. Once the
    branches read correctly in both apps it can be dropped by hand.
    """
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'fm_contract' AND column_name = 'branch_id'
    """)
    if not cr.fetchone():
        _logger.info("Aabaan branch: no legacy fm_contract.branch_id column, "
                     "nothing to carry over.")
        return

    cr.execute("""
        UPDATE sale_order so
           SET branch_id = fc.branch_id
          FROM fm_contract fc
         WHERE fc.sale_order_id = so.id
           AND fc.branch_id IS NOT NULL
           AND so.branch_id IS NULL
    """)
    moved = cr.rowcount

    cr.execute("""
        SELECT count(*) FROM fm_contract fc
          JOIN sale_order so ON so.id = fc.sale_order_id
         WHERE fc.branch_id IS NOT NULL
           AND so.branch_id IS DISTINCT FROM fc.branch_id
    """)
    mismatched = cr.fetchone()[0]

    _logger.info(
        "Aabaan branch: carried branch onto %s sale order(s); %s contract(s) "
        "still differ from their order (a branch was already set there and "
        "was left alone). The legacy fm_contract.branch_id column is kept "
        "for now and can be dropped once the branches read correctly.",
        moved, mismatched)
