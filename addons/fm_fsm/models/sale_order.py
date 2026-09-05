# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models

from .fm_visit_schedule_mixin import ROLLING_HORIZON_DAYS


class SaleOrder(models.Model):
    """Visits follow the sale order.

    A contract is a sale order, so the visit schedule hangs off the order
    too: the thing the customer agreed to is the thing that says when
    someone turns up. Confirming the order both activates the contract and
    fills its calendar, which is why there is no separate "generate the
    schedule" step to forget.

    The scheduling itself is in fm.visit.schedule.mixin — one generator for
    the whole platform, which is the point of this consolidation.
    """

    _inherit = ["sale.order", "fm.visit.schedule.mixin"]
    _name = "sale.order"

    # fm_-prefixed, like everything else this platform adds to sale.order:
    # sale_project already puts task fields on the order, and quietly
    # shadowing one of them would break native behaviour with no error.
    fm_task_ids = fields.One2many(
        "project.task", "fm_contract_order_id", string="Visits / Work Orders"
    )
    fm_task_count = fields.Integer(compute="_compute_fm_task_count")
    planned_visit_count = fields.Integer(compute="_compute_planned_visit_count")

    def _compute_fm_task_count(self):
        groups = self.env["project.task"]._read_group(
            [("fm_contract_order_id", "in", self.ids)], ["fm_contract_order_id"], ["__count"]
        )
        counts = {order.id: count for order, count in groups}
        for order in self:
            order.fm_task_count = counts.get(order.id, 0)

    @api.depends(
        "visit_frequency", "custom_interval_days",
        "fm_asset_ids", "fm_start_date", "fm_end_date",
    )
    def _compute_planned_visit_count(self):
        for order in self:
            order.planned_visit_count = order._fm_planned_visit_count()

    # ------------------------------------------------------------------
    # What the shared generator asks of us
    # ------------------------------------------------------------------
    def _fm_covered_assets(self):
        return self.fm_asset_ids

    def _fm_term(self):
        return self.fm_start_date, self.fm_end_date

    def _fm_contract_ref(self):
        return self.fm_contract_number or self.name

    def _fm_visit_link_vals(self):
        return {"fm_contract_order_id": self.id}

    def _fm_company(self):
        return self.company_id or self.env.company

    # ------------------------------------------------------------------
    # Confirming the order fills the calendar
    # ------------------------------------------------------------------
    def action_confirm(self):
        res = super().action_confirm()
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=ROLLING_HORIZON_DAYS)
        for order in self:
            if order.is_fm_contract and order.auto_schedule:
                order._generate_schedule(horizon_end=horizon)
        return res

    @api.model
    def _cron_auto_schedule(self):
        """Keep a rolling horizon of planned visits populated for active,
        auto-scheduled contracts.

        Shipped switched off. Turning it on is a deliberate decision: it
        writes visits into people's calendars unattended, and a schedule
        that appears with nothing on screen to say what made it is worse
        than one somebody pressed a button for.
        """
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=ROLLING_HORIZON_DAYS)
        contracts = self.search([
            ("is_fm_contract", "=", True),
            ("fm_lifecycle", "=", "active"),
            ("auto_schedule", "=", True),
        ])
        contracts._generate_schedule(horizon_end=horizon)
