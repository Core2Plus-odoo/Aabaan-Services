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
    fm_contract_id = fields.Many2one(
        "fm.contract", string="AMC Contract", index=True, tracking=True
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

    @api.onchange("fm_contract_id")
    def _onchange_fm_contract_id(self):
        """Pull the customer from the AMC contract's sales document."""
        for task in self:
            if task.fm_contract_id and task.fm_contract_id.partner_id:
                task.partner_id = task.fm_contract_id.partner_id
