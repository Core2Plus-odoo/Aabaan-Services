# -*- coding: utf-8 -*-
from odoo import api, fields, models

from odoo.addons.fm_contract.models.fm_sla_rule import SEVERITY
from odoo.addons.fm_fsm.models.fm_visit_schedule_mixin import (
    TIME_SLOTS,
    slot_for_hour,
)


class ProjectTask(models.Model):
    """Facility Management fields grafted onto the native Field Service task.

    Standard-first re-base: work orders are executed as native FSM tasks
    (``project.task`` with ``is_fsm=True``). This ``_inherit`` adds the FM
    domain context — the asset being serviced, its contract, severity and
    service line — without a bespoke state machine. Stage/scheduling/SLA are
    handled by native Field Service, SLA policies and recurrence.
    """

    _inherit = "project.task"

    fm_asset_id = fields.Many2one(
        "fm.asset",
        string="Asset",
        index=True,
        tracking=True,
        help="Facility asset this job services.",
    )
    # "Asset Service Line", not "Service Line": this database also carries a
    # manual x_service_line on project.task with that label, and Odoo warns
    # about the clash at every registry load. This one is the asset's, which
    # is the more precise name anyway.
    fm_service_line = fields.Selection(
        related="fm_asset_id.service_line", store=True, index=True,
        string="Asset Service Line",
    )
    fm_location_id = fields.Many2one(
        related="fm_asset_id.location_fm_id", store=True, string="Asset Location"
    )
    fm_contract_order_id = fields.Many2one(
        "sale.order",
        string="AMC Contract",
        index=True,
        tracking=True,
        domain="[('is_fm_contract', '=', True)]",
        help="The contract this visit belongs to. A contract is a sale "
             "order, so this is the order the customer agreed to.",
    )
    # Deliberately NOT project.task.sale_order_id: that native field means
    # "the order this task bills to", derived from the sale order line that
    # created the task, and it is computed. A visit generated from an AMC
    # contract is not necessarily billed from a line on that order, so the
    # two answers can differ and only one of them is the contract.
    fm_contract_id = fields.Many2one(
        "fm.contract", string="AMC Contract (legacy)", index=True, tracking=True
    )
    fm_severity = fields.Selection(
        SEVERITY, string="Severity", default="p3_medium", tracking=True, index=True
    )
    fm_time_slot = fields.Selection(
        TIME_SLOTS,
        string="Time Slot",
        compute="_compute_fm_time_slot",
        store=True,
        index=True,
        help="Morning, Day or Night, derived from the planned start time.",
    )
    fm_wo_type = fields.Selection(
        [
            ("reactive", "Reactive"),
            ("ppm", "PPM / Planned"),
            ("compliance", "Compliance"),
            ("project", "Project"),
            ("inspection", "Inspection"),
        ],
        string="Work Type",
        default="reactive",
        tracking=True,
    )

    def _fm_contract_order(self):
        """The sale order behind this visit's contract, whichever link is set.

        A visit reaches its contract one of two ways: ``fm_contract_order_id``
        for a contract written in Sales, or the legacy ``fm_contract_id``,
        which wraps a sale order by delegation. Anything that wants the
        contract's order lines, customer or currency should ask here rather
        than pick one field and quietly return nothing for visits linked the
        other way.
        """
        self.ensure_one()
        return self.fm_contract_order_id or self.fm_contract_id.sale_order_id

    @api.onchange("fm_contract_order_id")
    def _onchange_fm_contract_order_id(self):
        """Pull the customer from the contract's sale order."""
        for task in self:
            if task.fm_contract_order_id and task.fm_contract_order_id.partner_id:
                task.partner_id = task.fm_contract_order_id.partner_id

    @api.onchange("fm_contract_id")
    def _onchange_fm_contract_id(self):
        """Pull the customer from the legacy contract's sales document."""
        for task in self:
            if task.fm_contract_id and task.fm_contract_id.partner_id:
                task.partner_id = task.fm_contract_id.partner_id

    @api.depends("planned_date_begin")
    def _compute_fm_time_slot(self):
        """Tag every job with exactly one slot, read off its planned start.

        Derived rather than stored independently so the tag cannot go stale:
        a dispatcher who drags a job from the morning to the night slot on
        the planning Gantt gets the tag moved with it, and a job created by
        hand is tagged without anyone remembering to.

        The hour is read straight off ``planned_date_begin``, which is the
        same value the generator writes from the contract's start time. Note
        that field is a UTC Datetime while the generator treats the contract
        time as a wall clock, so both sides share one interpretation -- see
        CLAUDE.md section 4; correcting that is a separate change, because it
        would move every already-planned visit.
        """
        for task in self:
            if task.planned_date_begin:
                begin = task.planned_date_begin
                task.fm_time_slot = slot_for_hour(begin.hour + begin.minute / 60.0)
            else:
                task.fm_time_slot = False
