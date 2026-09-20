# -*- coding: utf-8 -*-
"""Drop the legacy ``fm.contract`` model and everything hanging off it.

Runs before the ORM syncs the registry, because the ORM cannot do this
itself: removing a field from Python leaves its column, and its foreign
key, in place — so ``fm_contract``'s table could not be dropped while
other tables still pointed at it.

**Order matters, and this one is not arbitrary** (see CLAUDE.md §5). The
dangerous part is not the table, it is the cascade: ``fm.sla.rule``,
``fm.contract.penalty`` and ``fm.contract.agreement.line`` each carried
``contract_id ... ondelete="cascade"``, and each of those tables holds
the rows of *current* contracts too. Deleting the contract rows first
would silently take live SLA rules, penalty clauses and agreement
articles with them. So the child links go first, and each goes as a
whole column, which takes its foreign key with it.

Rows that belonged *only* to a legacy contract are deleted rather than
orphaned. A rule with no ``order_id`` once its ``contract_id`` is gone
would be invisible in every view and counted by nothing — litter, and
the kind that is frightening to clean up later because nobody can say
what it was for.

The remaining references are **discovered, not listed**. Two of this
model's many2many tables were auto-named by Odoo rather than declared
(``asset_ids``, ``customer_contact_ids``), so a hardcoded list is a list
of guesses; ``pg_constraint`` knows the real answer and also catches any
link added since this was written.

Everything is ``IF EXISTS`` / existence-checked, so a database that
never had the model, or a re-run, is a no-op rather than an error.
"""
import logging

_logger = logging.getLogger(__name__)

TABLE = "fm_contract"

# The children that cascade from fm_contract AND hold live rows of their
# own. {table: (link column, the column that means "this row is current")}
CHILD_LINKS = {
    "fm_sla_rule": ("contract_id", "order_id"),
    "fm_contract_penalty": ("contract_id", "order_id"),
    "fm_contract_agreement_line": ("contract_id", "order_id"),
}


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return cr.fetchone()[0] is not None


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def _referencing_columns(cr, table):
    """[(table, column)] for every foreign key pointing at ``table``."""
    cr.execute("""
        SELECT src.relname, att.attname
          FROM pg_constraint con
          JOIN pg_class src ON src.oid = con.conrelid
          JOIN pg_class tgt ON tgt.oid = con.confrelid
          JOIN pg_attribute att
            ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
         WHERE con.contype = 'f'
           AND tgt.relname = %s
           AND src.relname <> %s
    """, (table, table))
    return cr.fetchall()


def _is_relation_table(cr, table):
    """A many2many join table: two columns, both foreign keys."""
    cr.execute("""
        SELECT count(*) FROM information_schema.columns WHERE table_name = %s
    """, (table,))
    if cr.fetchone()[0] != 2:
        return False
    cr.execute("""
        SELECT count(*) FROM pg_constraint con
          JOIN pg_class src ON src.oid = con.conrelid
         WHERE con.contype = 'f' AND src.relname = %s
    """, (table,))
    return cr.fetchone()[0] == 2


def migrate(cr, version):
    if not version:
        return

    if not _table_exists(cr, TABLE):
        _logger.info("fm.contract table is already gone; nothing to drop.")
        return

    cr.execute("SELECT count(*) FROM fm_contract")
    _logger.info("Retiring fm.contract: %s row(s).", cr.fetchone()[0])

    # 1. The cascading children, before anything deletes a contract row.
    for table, (link, live) in CHILD_LINKS.items():
        if not (_table_exists(cr, table) and _column_exists(cr, table, link)):
            continue
        cr.execute("DELETE FROM %s WHERE %s IS NOT NULL AND %s IS NULL" % (table, link, live))
        _logger.info("fm.contract: deleted %s legacy-only row(s) from %s.", cr.rowcount, table)
        cr.execute("ALTER TABLE %s DROP COLUMN IF EXISTS %s" % (table, link))

    # 2. Everything else that still points here, found rather than guessed.
    #    A two-column all-foreign-key table is a many2many join and goes
    #    whole; anything else keeps its rows and loses only the link.
    for table, column in _referencing_columns(cr, TABLE):
        if _is_relation_table(cr, table):
            _logger.info("fm.contract: dropping join table %s.", table)
            cr.execute("DROP TABLE IF EXISTS %s" % table)
        else:
            _logger.info("fm.contract: dropping %s.%s.", table, column)
            cr.execute("ALTER TABLE %s DROP COLUMN IF EXISTS %s" % (table, column))

    # 3. The stored related on the materials line. It followed
    #    project_task.fm_contract_id rather than fm_contract itself, so it
    #    has no foreign key here and step 2 does not see it.
    if _table_exists(cr, "fm_visit_material"):
        cr.execute("ALTER TABLE fm_visit_material DROP COLUMN IF EXISTS contract_id")

    # 4. Chatter, activities and attachments. These find their record by
    #    (model, res_id) with no foreign key, so nothing breaks if they are
    #    left -- but they would be unreachable rows about a model that no
    #    longer exists.
    cr.execute("DELETE FROM mail_message WHERE model = 'fm.contract'")
    cr.execute("DELETE FROM mail_followers WHERE res_model = 'fm.contract'")
    cr.execute("DELETE FROM mail_activity WHERE res_model = 'fm.contract'")
    cr.execute("DELETE FROM ir_attachment WHERE res_model = 'fm.contract'")

    # 5. The table itself. CASCADE is a backstop only: step 2 should have
    #    left nothing pointing here, and if something did, taking that one
    #    constraint with it beats a failed production upgrade.
    cr.execute("DROP TABLE IF EXISTS fm_contract CASCADE")

    # 6. The registry's bookkeeping. ir_model_fields and the ir.rule /
    #    ir.model.access rows cascade from ir_model, but the xmlid anchors in
    #    ir_model_data do not -- and a dangling anchor makes the next upgrade
    #    try to load a record whose model is gone.
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE model = 'fm.contract'
           OR (model = 'ir.model' AND name = 'model_fm_contract')
           OR (model = 'ir.model.fields' AND name LIKE 'field_fm_contract__%')
    """)
    cr.execute("DELETE FROM ir_model WHERE model = 'fm.contract'")

    _logger.info("fm.contract retired.")
