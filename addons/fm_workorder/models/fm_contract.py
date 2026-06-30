# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# How many work orders per asset per year for each cadence.
FREQUENCY_PER_YEAR = {
    "monthly": 12,
    "bi_monthly": 6,
    "quarterly": 4,
    "semi_annual": 2,
    "annual": 1,
}


class FmContract(models.Model):
    """Extends fm.contract with work-order back-references (resolving the
    contract↔work-order circular dependency) and contract-level scheduling:
    generate the planned preventive work orders for the covered assets across
    the contract term.
    """

    _inherit = "fm.contract"

    workorder_ids = fields.One2many("fm.workorder", "contract_id", string="Work Orders")
    workorder_count = fields.Integer(compute="_compute_workorder_count")

    # Scheduling configuration
    visit_frequency = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("bi_monthly", "Every 2 Months"),
            ("quarterly", "Quarterly"),
            ("semi_annual", "Semi-Annual"),
            ("annual", "Annual"),
        ],
        string="Visit Frequency",
        default="monthly",
        help="Cadence used by 'Generate Work Orders' to schedule planned visits per covered asset.",
    )
    preferred_technician_id = fields.Many2one("hr.employee", string="Preferred Technician")
    planned_wo_count = fields.Integer(compute="_compute_planned_wo_count")

    def _compute_workorder_count(self):
        groups = self.env["fm.workorder"]._read_group(
            [("contract_id", "in", self.ids)], ["contract_id"], ["__count"]
        )
        counts = {c.id: n for c, n in groups}
        for contract in self:
            contract.workorder_count = counts.get(contract.id, 0)

    @api.depends("visit_frequency", "asset_ids")
    def _compute_planned_wo_count(self):
        for contract in self:
            per_year = FREQUENCY_PER_YEAR.get(contract.visit_frequency, 12)
            contract.planned_wo_count = per_year * len(contract.asset_ids)

    def action_view_workorders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Work Orders"),
            "res_model": "fm.workorder",
            "view_mode": "calendar,list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id, "default_customer_id": self.partner_id.id},
        }

    # ------------------------------------------------------------------
    # Contract-level scheduling
    # ------------------------------------------------------------------
    def action_generate_workorders(self):
        """Create planned (PPM) work orders for every covered asset, evenly
        spaced across the contract term at the chosen frequency.
        """
        self.ensure_one()
        if not self.asset_ids:
            raise UserError(_("Add at least one covered asset before generating work orders."))
        if not self.start_date or not self.end_date or self.end_date <= self.start_date:
            raise UserError(_("Set a valid start and end date on the contract first."))

        # Scale the per-year cadence to the actual contract length.
        per_year = FREQUENCY_PER_YEAR.get(self.visit_frequency, 12)
        total_days = (self.end_date - self.start_date).days
        count = max(1, round(per_year * (total_days / 365.0)))
        interval_days = total_days / count

        Wo = self.env["fm.workorder"]
        company = self.sale_order_id.company_id or self.env.company
        tech = self.preferred_technician_id

        vals_list = []
        for asset in self.asset_ids:
            for index in range(count):
                visit_date = self.start_date + timedelta(days=round(interval_days * index))
                start_dt = datetime.combine(visit_date, time(9, 0))
                vals_list.append({
                    "wo_type": "ppm",
                    "severity": "p3_medium",
                    "asset_id": asset.id,
                    "customer_id": self.partner_id.id,
                    "contract_id": self.id,
                    "company_id": company.id,
                    "technician_id": tech.id if tech else False,
                    "stage": "assigned" if tech else "draft",
                    "problem_description": _("Planned visit for %(asset)s under contract %(ref)s")
                    % {"asset": asset.display_name, "ref": self.contract_number},
                    "schedule_date_start": start_dt,
                    "schedule_date_end": start_dt + timedelta(hours=1),
                })
        created = Wo.create(vals_list)
        self.message_post(body=_("%s planned work order(s) generated.") % len(created))

        return {
            "type": "ir.actions.act_window",
            "name": _("Scheduled Work Orders"),
            "res_model": "fm.workorder",
            "view_mode": "calendar,list,form",
            "domain": [("id", "in", created.ids)],
            "context": {"default_contract_id": self.id},
        }
