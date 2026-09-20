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

Scoped to ``sale.order`` deliberately. The same upgrade logs a second
collision, ``x_plan4_id`` vs ``department_id`` on
``account.analytic.line`` -- but that one is a manual field *Odoo
itself* creates for an analytic plan, so renaming it would be meddling
with a native mechanism to silence a warning. Not ours to touch.
"""
import logging

_logger = logging.getLogger(__name__)

MODEL = "sale.order"


def migrate(cr, version):
    if not version:
        return

    # Manual fields on sale.order whose label matches a field some module
    # declares. Compared on label, because that is what a user sees and
    # what the collision is about.
    cr.execute("""
        SELECT manual.id, manual.name, manual.field_description, module.name
          FROM ir_model_fields manual
          JOIN ir_model_fields module
            ON module.model = manual.model
           AND module.field_description = manual.field_description
           AND module.id <> manual.id
           AND module.state = 'base'
         WHERE manual.model = %s
           AND manual.state = 'manual'
           AND manual.field_description NOT LIKE '%%(' || manual.name || ')'
    """, (MODEL,))
    rows = cr.fetchall()

    if not rows:
        _logger.info("No manual field on %s shadows a module field's label.", MODEL)
        return

    for field_id, technical_name, label, shadowed in rows:
        new_label = "%s (%s)" % (label, technical_name)
        cr.execute(
            "UPDATE ir_model_fields SET field_description = %s WHERE id = %s",
            (new_label, field_id),
        )
        _logger.info(
            "%s: manual field %s shadowed %s under the label %r; relabelled to %r.",
            MODEL, technical_name, shadowed, label, new_label,
        )
