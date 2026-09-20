# -*- coding: utf-8 -*-
"""Tell a manual field apart from the module field it shadows.

The production upgrade logs this, five times:

    Two fields (x_visit_frequency, visit_frequency) of sale.order()
    have the same label: Visit Frequency. [Modules: None and fm_fsm]

``Modules: None`` means ``x_visit_frequency`` is a manual field created
on the database -- Studio, or by hand -- not something any module here
declares. It is a leftover: nothing in this repository reads it, and
fm_fsm's own ``visit_frequency`` is the one the visit generator uses.

Two fields with the same label on the same form is how the wrong one
gets filled in. That now matters more than it did: a contract profile
on the quotation template fills ``visit_frequency``, so a user who
types into the shadow field gets a schedule that ignores them, with no
error anywhere.

This does not delete anything. A manual field owns a real column with
real data in it, and whether that data is still wanted is the client's
call, not a migration's. It only appends the technical name to the
manual field's label, so the two are told apart on sight and the
warning stops:

    Visit Frequency  ->  Visit Frequency (x_visit_frequency)

**``field_description`` is jsonb, not text.** It is a translatable
field, so Odoo 19 stores it as ``{"en_US": "Visit Frequency"}`` and
every comparison has to go through ``->>`` and every write through
``jsonb_set``. The first version of this file used ``LIKE`` straight on
the column and took the production build down with
``operator does not exist: jsonb !~~ text`` -- the local fixture had
declared the column ``varchar``, so the test could never have caught
it. Any migration touching a translatable column needs a jsonb fixture.

Only the ``en_US`` entry is compared and rewritten: that is the label
the warning is about and the one users see on this database. A manual
field with no ``en_US`` key simply does not match and is left alone.

Scoped to ``sale.order`` deliberately. The same upgrade logs a second
collision, ``x_plan4_id`` vs ``department_id`` on
``account.analytic.line`` -- but that one is a manual field *Odoo
itself* creates for an analytic plan, so renaming it would be meddling
with a native mechanism to silence a warning. Not ours to touch.
"""
import logging

_logger = logging.getLogger(__name__)

MODEL = "sale.order"
LANG = "en_US"


def migrate(cr, version):
    if not version:
        return

    # Manual fields on sale.order whose English label matches the English
    # label of a field some module declares. Compared on the label, because
    # that is what a user sees and what the collision is about.
    cr.execute("""
        SELECT manual.id,
               manual.name,
               manual.field_description ->> %(lang)s,
               module.name
          FROM ir_model_fields manual
          JOIN ir_model_fields module
            ON module.model = manual.model
           AND module.id <> manual.id
           AND module.state = 'base'
           AND module.field_description ->> %(lang)s
             = manual.field_description ->> %(lang)s
         WHERE manual.model = %(model)s
           AND manual.state = 'manual'
           AND manual.field_description ->> %(lang)s IS NOT NULL
    """, {"lang": LANG, "model": MODEL})
    rows = cr.fetchall()

    relabelled = 0
    for field_id, technical_name, label, shadowed in rows:
        suffix = "(%s)" % technical_name
        if label.endswith(suffix):
            continue  # already done on an earlier run
        new_label = "%s %s" % (label, suffix)
        cr.execute("""
            UPDATE ir_model_fields
               SET field_description = jsonb_set(
                       field_description, %(path)s, to_jsonb(%(label)s::text))
             WHERE id = %(id)s
        """, {"path": "{%s}" % LANG, "label": new_label, "id": field_id})
        relabelled += 1
        _logger.info(
            "%s: manual field %s shadowed %s under the label %r; relabelled to %r.",
            MODEL, technical_name, shadowed, label, new_label,
        )

    if not relabelled:
        _logger.info("No manual field on %s shadows a module field's label.", MODEL)
