# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

HEALTH_BANDS = [
    ("healthy", "Healthy"),
    ("watch", "Watch"),
    ("at_risk", "At Risk"),
    ("critical", "Critical"),
]


class FmCeoDashboard(models.AbstractModel):
    """Data provider for the CEO dashboard OWL client action.

    Read-only aggregation over native records (fm.contract / project.task /
    fm.compliance.certificate / account.move), scoped to the user's companies.
    Everything is guarded so the dashboard degrades gracefully if an optional
    module (branch/compliance) is absent.
    """

    _name = "fm.ceo.dashboard"
    _description = "FM CEO Dashboard Data"

    @api.model
    def get_ceo_data(self, branch_id=None):
        companies = self.env.companies
        company = self.env.company
        currency = company.currency_id
        today = fields.Date.context_today(self)
        year_start = today.replace(month=1, day=1)

        Contract = self.env["fm.contract"].sudo()
        Task = self.env["project.task"].sudo()

        contract_dom = [("sale_order_id.company_id", "in", companies.ids)]
        task_dom = [("company_id", "in", companies.ids), ("fm_wo_type", "!=", False)]

        # Optional branch scoping
        branches = []
        if "fm.branch" in self.env:
            branches = [
                {"id": b.id, "name": b.name}
                for b in self.env["fm.branch"].sudo().search([("company_id", "in", companies.ids)])
            ]
        if branch_id and "branch_id" in Contract._fields:
            contract_dom += [("branch_id", "=", branch_id)]
        if branch_id and "branch_id" in Task._fields:
            task_dom += [("branch_id", "=", branch_id)]

        active = Contract.search(contract_dom + [("state", "=", "active")])
        acv = sum(active.mapped("acv"))
        tcv = sum(active.mapped("tcv"))

        # Contract health distribution
        band_labels = dict(HEALTH_BANDS)
        health = []
        total_active = len(active) or 1
        for band, _label in HEALTH_BANDS:
            n = len(active.filtered(lambda c: c.health_band == band))
            health.append({
                "band": band,
                "label": band_labels[band],
                "count": n,
                "pct": round(n / total_active * 100),
            })

        # Renewals due in the next 90 days
        renewals = active.filtered(
            lambda c: c.days_to_renewal is not False and 0 <= (c.days_to_renewal or 999) <= 90
        )
        renewal_rows = [
            {
                "id": c.id,
                "name": c.contract_number,
                "partner": c.partner_id.display_name,
                "days": int(c.days_to_renewal or 0),
                "acv": c.acv,
            }
            for c in renewals.sorted(key=lambda c: c.days_to_renewal or 0)[:8]
        ]

        # Portfolio value by branch
        by_branch = []
        if branches:
            for b in branches:
                b_contracts = active.filtered(lambda c: c.branch_id.id == b["id"]) \
                    if "branch_id" in Contract._fields else Contract
                val = sum(b_contracts.mapped("acv"))
                if val:
                    by_branch.append({"label": b["name"], "value": val})
            by_branch.sort(key=lambda x: x["value"], reverse=True)

        # Operations: open work orders by severity
        sev_labels = dict(Task._fields["fm_severity"].selection)
        open_tasks = Task.search(task_dom + [("stage_id.fold", "=", False)])
        ops = []
        for code, label in Task._fields["fm_severity"].selection:
            n = len(open_tasks.filtered(lambda t: t.fm_severity == code))
            ops.append({"code": code, "label": sev_labels.get(code, label), "count": n})
        open_critical = len(open_tasks.filtered(lambda t: t.fm_severity in ("p1_critical", "p2_high")))

        since_month = today.replace(day=1)
        completed_month = Task.search_count(
            task_dom + [("stage_id.fold", "=", True), ("write_date", ">=", fields.Datetime.to_datetime(since_month))]
        )

        # Compliance risk
        compliance = {"expiring": 0, "expired": 0, "valid": 0}
        if "fm.compliance.certificate" in self.env:
            Cert = self.env["fm.compliance.certificate"].sudo()
            cdom = [("company_id", "in", companies.ids)]
            compliance = {
                "expiring": Cert.search_count(cdom + [("state", "=", "expiring_soon")]),
                "expired": Cert.search_count(cdom + [("state", "=", "expired")]),
                "valid": Cert.search_count(cdom + [("state", "=", "valid")]),
            }

        # Revenue YTD (posted customer invoices)
        revenue_ytd = 0.0
        Move = self.env["account.move"].sudo()
        moves = Move.search([
            ("company_id", "in", companies.ids),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", year_start),
        ])
        revenue_ytd = sum(moves.mapped("amount_untaxed_signed"))

        return {
            "currency": currency.symbol or currency.name,
            "company_label": "All Companies" if len(companies) > 1 else company.name,
            "branches": branches,
            "branch_id": branch_id or False,
            "kpis": {
                "acv": acv,
                "tcv": tcv,
                "active_contracts": len(active),
                "revenue_ytd": revenue_ytd,
                "open_critical": open_critical,
                "completed_month": completed_month,
                "renewals_90d": len(renewals),
                "compliance_expired": compliance["expired"],
            },
            "health": health,
            "renewals": renewal_rows,
            "by_branch": by_branch,
            "ops": ops,
            "compliance": compliance,
        }
