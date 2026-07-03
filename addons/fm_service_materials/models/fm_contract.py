# -*- coding: utf-8 -*-
from odoo import _, models


class FmContract(models.Model):
    _inherit = "fm.contract"

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
        open_tasks = self.task_ids.filtered(lambda t: not t.stage_id.fold)
        open_tasks._fm_autoload_materials()
        self.message_post(
            body=_("Expected materials loaded on %s open visit(s).") % len(open_tasks)
        )
        return True
