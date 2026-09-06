# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

from .fm_visit_schedule_mixin import ROLLING_HORIZON_DAYS


class FmContract(models.Model):
    """Visit scheduling for the legacy contract model.

    The scheduling itself is in fm.visit.schedule.mixin, shared with
    contracts written in Sales. Only the accessors are here, because this
    model spells the same things differently (``asset_ids``, ``start_date``,
    ``end_date``). When this model is retired, this file goes with it and the
    generator is untouched.
    """

    _inherit = ["fm.contract", "fm.visit.schedule.mixin"]
    _name = "fm.contract"

    fm_task_ids = fields.One2many("project.task", "fm_contract_id", string="Visits / Work Orders")
    fm_task_count = fields.Integer(compute="_compute_fm_task_count")
    planned_visit_count = fields.Integer(compute="_compute_planned_visit_count")

    def _compute_fm_task_count(self):
        groups = self.env["project.task"]._read_group(
            [("fm_contract_id", "in", self.ids)], ["fm_contract_id"], ["__count"]
        )
        counts = {c.id: n for c, n in groups}
        for contract in self:
            contract.fm_task_count = counts.get(contract.id, 0)

    @api.depends("visit_frequency", "custom_interval_days", "asset_ids", "start_date", "end_date")
    def _compute_planned_visit_count(self):
        for contract in self:
            contract.planned_visit_count = contract._fm_planned_visit_count()

    # ------------------------------------------------------------------
    # What the shared generator asks of us
    # ------------------------------------------------------------------
    def _fm_covered_assets(self):
        return self.asset_ids

    def _fm_term(self):
        return self.start_date, self.end_date

    def _fm_contract_ref(self):
        return self.contract_number

    def _fm_visit_link_vals(self):
        return {"fm_contract_id": self.id}

    def _fm_company(self):
        return self.sale_order_id.company_id or self.env.company

    def action_activate(self):
        res = super().action_activate()
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=ROLLING_HORIZON_DAYS)
        for contract in self:
            if contract.auto_schedule:
                contract._generate_schedule(horizon_end=horizon)
        return res
