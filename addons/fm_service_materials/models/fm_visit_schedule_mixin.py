# -*- coding: utf-8 -*-
"""Expected materials follow the visit schedule.

Both contract models get the same two methods. They are written out on each
model rather than shared through a base class, and that is deliberate — see
the two things that do NOT work below.

**Not by extending ``fm.visit.schedule.mixin``.** An Odoo model composes its
class from the abstract models it inherits *at the moment it is built*.
``sale.order`` and ``fm.contract`` are both built in fm_fsm, before this
module loads, so extending the abstract mixin here would register, raise
nothing, and never run.

**Not by mixing a plain Python class into the model bases either** — i.e.
``class SaleOrder(MaterialsOnSchedule, models.Model)``. That reads like the
obvious fix and it takes production down: a plain class carries an ``object``
instance layout, and when the registry rebuilds the model with
``model_cls.__bases__ = model_cls._base_classes__`` Python refuses the
assignment with ``TypeError: __bases__ assignment: 'SaleOrder' object layout
differs from 'SaleOrder'``. The registry then fails to load and the database
will not start. It cannot be caught by compiling or parsing — only by
building the registry.

So: plain ``_inherit`` extensions, which is all this ever needed. The bodies
are one line each, delegating to the module-level helpers so the logic is
still written once.
"""
from odoo import _, models


def _autoload_materials(created):
    """Populate expected materials on freshly scheduled visits."""
    if created:
        created._fm_autoload_materials()
    return created


def _load_open_visit_materials(contract):
    """Populate expected materials on a contract's open visits."""
    contract.ensure_one()
    open_tasks = contract.fm_task_ids.filtered(lambda t: not t.stage_id.fold)
    open_tasks._fm_autoload_materials()
    contract.message_post(
        body=_("Expected materials loaded on %s open visit(s).") % len(open_tasks)
    )
    return True


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _generate_schedule(self, horizon_end=None):
        return _autoload_materials(super()._generate_schedule(horizon_end=horizon_end))

    def action_load_visit_materials(self):
        return _load_open_visit_materials(self)


class FmContract(models.Model):
    _inherit = "fm.contract"

    def _generate_schedule(self, horizon_end=None):
        return _autoload_materials(super()._generate_schedule(horizon_end=horizon_end))

    def action_load_visit_materials(self):
        return _load_open_visit_materials(self)
