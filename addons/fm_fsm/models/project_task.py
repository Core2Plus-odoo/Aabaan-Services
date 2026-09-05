# -*- coding: utf-8 -*-
from odoo import api, fields, models

from odoo.addons.fm_contract.models.fm_sla_rule import SEVERITY


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
    fm_service_line = fields.Selection(
        related="fm_asset_id.service_line", store=True, index=True, string="Service Line"
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
