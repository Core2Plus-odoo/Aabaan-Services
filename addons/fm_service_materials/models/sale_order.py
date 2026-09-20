# -*- coding: utf-8 -*-
"""Expected materials follow the visit schedule.

Generating a contract's visits fills in the materials each one is expected
to consume, and a button re-fills the open ones.

This is a plain ``_inherit`` on ``sale.order``, and it has to stay one —
two tidier-looking alternatives are both wrong:

**Not by extending ``fm.visit.schedule.mixin``.** An Odoo model composes its
class from the abstract models it inherits *at the moment it is built*.
``sale.order`` is built in fm_fsm, before this module loads, so extending the
abstract mixin here would register, raise nothing, and never run.

**Not by mixing a plain Python class into the model bases either** — i.e.
``class SaleOrder(MaterialsOnSchedule, models.Model)``. That reads like the
obvious way to share a body across models and it takes production down: a
plain class carries an ``object`` instance layout, and when the registry
rebuilds the model with ``model_cls.__bases__ = model_cls._base_classes__``
Python refuses the assignment with ``TypeError: __bases__ assignment:
'SaleOrder' object layout differs from 'SaleOrder'``. The registry then fails
to load and the database will not start. It cannot be caught by compiling or
parsing — only by building the registry.

Both notes are kept although only one model carries these methods now: the
legacy ``fm.contract`` used to carry them too, and the next person who needs
the same behaviour on a second model will reach for exactly those two
shortcuts.
"""
from odoo import _, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _generate_schedule(self, horizon_end=None):
        created = super()._generate_schedule(horizon_end=horizon_end)
        if created:
            created._fm_autoload_materials()
        return created

    def action_load_visit_materials(self):
        """Populate expected materials on this contract's open visits."""
        self.ensure_one()
        open_tasks = self.fm_task_ids.filtered(lambda t: not t.stage_id.fold)
        open_tasks._fm_autoload_materials()
        self.message_post(
            body=_("Expected materials loaded on %s open visit(s).") % len(open_tasks)
        )
        return True
