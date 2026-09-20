# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models

from .fm_visit_schedule_mixin import ROLLING_HORIZON_DAYS, SLOT_START_HOUR


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

    # ------------------------------------------------------------------
    # The cadence half of a contract profile
    # ------------------------------------------------------------------
    # These mirror fm.visit.schedule.mixin's fields, redefined here so the
    # quotation template can fill them -- a compute may only assign the
    # fields it declares. Each stays readonly=False, so a contract that
    # needs a different cadence than its profile is one edit away.
    visit_frequency = fields.Selection(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    custom_interval_days = fields.Integer(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    visit_day_1 = fields.Integer(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    visit_day_2 = fields.Integer(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    fm_time_slot = fields.Selection(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    visit_start_time = fields.Float(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    visit_duration_hours = fields.Float(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )
    skip_weekends = fields.Boolean(
        compute="_compute_fm_schedule_from_template", store=True, readonly=False,
    )

    @api.depends("sale_order_template_id")
    def _compute_fm_schedule_from_template(self):
        """Fill the visit cadence from the order's contract profile.

        Same shape as fm_contract's _compute_fm_from_template, and the same
        reason: Odoo applies a quotation template through stored editable
        computes, so this reaches orders created by import or RPC too.

        The slot sets the start time here exactly as the form's onchange
        does -- the time is the single source of truth and the slot is its
        label -- because an onchange does not run for an order built by a
        profile without anybody opening it.
        """
        for order in self:
            profile = order.sale_order_template_id
            # _origin, not the field itself: a compute's own fields are
            # protected while it runs, and a protected read on an unsaved
            # record returns False rather than the stored value. See the
            # same note in fm_contract's _compute_fm_from_template.
            saved = order._origin
            if not profile or not profile.fm_is_contract_profile:
                # A compute must assign on every record, or a new order
                # comes back with these unset rather than defaulted.
                order.visit_frequency = saved.visit_frequency or "monthly"
                order.custom_interval_days = saved.custom_interval_days
                order.visit_day_1 = saved.visit_day_1 or 1
                order.visit_day_2 = saved.visit_day_2 or 15
                order.fm_time_slot = saved.fm_time_slot or "morning"
                order.visit_start_time = saved.visit_start_time or 8.0
                order.visit_duration_hours = saved.visit_duration_hours or 2.0
                # `or` cannot express a boolean whose default is True, and a
                # brand-new record has no _origin to read -- so fall back to
                # the field's own default rather than to False, which is
                # what making this field computed silently did.
                order.skip_weekends = saved.skip_weekends if saved else True
                continue
            order.visit_frequency = profile.fm_visit_frequency or "monthly"
            order.custom_interval_days = profile.fm_custom_interval_days
            order.visit_day_1 = profile.fm_visit_day_1 or 1
            order.visit_day_2 = profile.fm_visit_day_2 or 15
            order.fm_time_slot = profile.fm_time_slot or "morning"
            order.visit_start_time = SLOT_START_HOUR.get(order.fm_time_slot, 8.0)
            order.visit_duration_hours = profile.fm_visit_duration_hours or 2.0
            order.skip_weekends = profile.fm_skip_weekends
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
