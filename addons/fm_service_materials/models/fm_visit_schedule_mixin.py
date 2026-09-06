# -*- coding: utf-8 -*-
from odoo import _, models


class MaterialsOnSchedule:
    """Expected materials follow the visit schedule.

    A plain Python base class, not an Odoo ``AbstractModel``, and that is
    deliberate. Extending ``fm.visit.schedule.mixin`` from here would not
    reach ``sale.order`` or ``fm.contract``: an Odoo model composes its
    class from the abstract models it inherits *at the moment it is built*,
    and both of those were built in fm_fsm, before this module loads. The
    extension would register, no error would be raised, and the materials
    would silently stop loading.

    Mixing this class into both models instead makes the composition
    explicit and order-independent. Neither method reads anything
    model-specific: ``_generate_schedule`` and ``fm_task_ids`` are the shared
    scheduling interface, so the same body serves both.
    """

    def _generate_schedule(self, horizon_end=None):
        """After scheduling visits, auto-populate their expected materials from
        the service composition so the forecast has data."""
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


class SaleOrder(MaterialsOnSchedule, models.Model):
    _inherit = "sale.order"


class FmContract(MaterialsOnSchedule, models.Model):
    _inherit = "fm.contract"
