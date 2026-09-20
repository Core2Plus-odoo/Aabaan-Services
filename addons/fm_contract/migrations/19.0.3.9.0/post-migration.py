# -*- coding: utf-8 -*-
"""Tell the ported service-term fields apart from the Studio fields they shadow.

Porting the contracted service terms out of the Studio layer gave
``sale.order`` three fields whose labels already belonged to a manual
field on the database, and the production upgrade said so three times::

    Two fields (x_premises_type, fm_premises_type) of sale.order()
    have the same label: Premises Type. [Modules: None and fm_contract]

``Modules: None`` means the ``x_`` field is a manual field created on the
database through Studio -- not something any module here declares.

This is the same failure ``fm_fsm/migrations/19.0.3.4.0`` fixed for
``x_visit_frequency``, and it is worth saying plainly why it came back:
**porting a Studio field into a module recreates the collision every
time, because a good port keeps the label the user already knows.** The
warning is not the problem. The problem is two boxes with one name on
one form, where filling in the wrong one is silent -- and now more than
silent, because ``fm_premises_type`` is what a municipal visit floor
will read and ``x_premises_type`` is what nothing reads.

So every future step of this reconciliation ships one of these. Two of
the five new fields collided with nothing (the Studio labels for the
call-out allowance and the follow-up window differ from ours), which is
why the loop below compares labels rather than working from a list: a
hand-written list of the three we saw would miss the fourth.

This does not delete anything. A manual field owns a real column with
real data in it, and whether that data is still wanted is the client's
call, not a migration's. It only appends the technical name to the
manual field's label, so the two are told apart on sight::

    Premises Type  ->  Premises Type (x_premises_type)

**``field_description`` is jsonb, not text.** Odoo 19 stores a
translatable field as ``{"en_US": "Premises Type"}``, so every
comparison goes through ``->>`` and every write through ``jsonb_set``.
Using ``LIKE`` straight on the column took the production build down
once already (``operator does not exist: jsonb !~~ text``); the fixture
that missed it had declared the column ``varchar``, so the test could
never have failed.

Scoped to ``sale.order`` deliberately. The same upgrade logs a collision
between ``x_plan4_id`` and ``department_id`` on
``account.analytic.line`` -- but that manual field is one *Odoo itself*
creates for an analytic plan, so renaming it would be meddling with a
native mechanism to silence a warning. Not ours to touch.
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
            continue  # already done, here or by fm_fsm's earlier pass
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
