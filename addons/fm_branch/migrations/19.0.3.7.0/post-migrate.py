import logging

_logger = logging.getLogger(__name__)


def _has_column(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Give the existing records the branch they already state elsewhere.

    The branch dropdowns (Maintenance Calendar, Command Centre) filter on
    ``branch_id``, but almost every contract written before the field
    existed carries its emirate only in the Studio field
    ``x_emirate_regime``. Without this, picking a branch shows nearly
    nothing.

    Only empty branches are filled, never overwritten:

    - a contract from its ``x_emirate_regime``, matched to the branch of
      that emirate in the same company ("other" and blank stay unset);
    - a visit from its contract;
    - a customer invoice from the sale order behind its lines.
    """
    if _has_column(cr, "sale_order", "x_emirate_regime"):
        cr.execute("""
            UPDATE sale_order so
               SET branch_id = b.id
              FROM fm_branch b
             WHERE so.branch_id IS NULL
               AND b.emirate = so.x_emirate_regime
               AND b.company_id = so.company_id
               AND b.active
        """)
        _logger.info("Aabaan branch: %s contract(s) given their branch.", cr.rowcount)

    links = [c for c in ("fm_contract_order_id", "sale_order_id")
             if _has_column(cr, "project_task", c)]
    if links:
        order = "COALESCE(%s)" % ", ".join("t.%s" % c for c in links) if len(links) > 1 else "t.%s" % links[0]
        cr.execute("""
            UPDATE project_task t
               SET branch_id = so.branch_id
              FROM sale_order so
             WHERE t.branch_id IS NULL
               AND so.id = %s
               AND so.branch_id IS NOT NULL
        """ % order)
        _logger.info("Aabaan branch: %s visit(s) given their branch.", cr.rowcount)

    cr.execute("SELECT to_regclass('sale_order_line_invoice_rel')")
    if cr.fetchone()[0]:
        cr.execute("""
            UPDATE account_move am
               SET branch_id = src.branch_id
              FROM (
                    SELECT DISTINCT ON (aml.move_id) aml.move_id, so.branch_id
                      FROM account_move_line aml
                      JOIN sale_order_line_invoice_rel rel ON rel.invoice_line_id = aml.id
                      JOIN sale_order_line sol ON sol.id = rel.order_line_id
                      JOIN sale_order so ON so.id = sol.order_id
                     WHERE so.branch_id IS NOT NULL
                     ORDER BY aml.move_id, aml.id
                   ) src
             WHERE am.id = src.move_id
               AND am.branch_id IS NULL
               AND am.move_type IN ('out_invoice', 'out_refund')
        """)
        _logger.info("Aabaan branch: %s invoice(s) given their branch.", cr.rowcount)
