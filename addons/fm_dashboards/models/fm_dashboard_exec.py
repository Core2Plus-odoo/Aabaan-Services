# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class FmDashboardExec(models.AbstractModel):
    """Data provider for the Executive Dashboard OWL client action (brief §7.1).

    Read-only aggregation over contracts and **native Field Service tasks**
    (``project.task``), scoped to the user's allowed companies. Re-based off the
    retired custom fm.workorder model: work orders are native FSM tasks, so the
    dashboard reflects the real record and all native reporting.
    """

    _name = "fm.dashboard.exec"
    _description = "FM Executive Dashboard Data"

    @api.model
    def get_dashboard_data(self, branch_id=None):
        companies = self.env.companies
        currency = self.env.company.currency_id
        today = fields.Date.context_today(self)
        since = fields.Datetime.to_datetime(today - relativedelta(days=90))
        Contract = self.env["fm.contract"].sudo()
        Task = self.env["project.task"].sudo()
        has_rating = "rating_last_value" in Task._fields

        # fm.contract company is delegated through the sale order
        contract_dom = [("sale_order_id.company_id", "in", companies.ids)]

        # Scope tasks to the FM Field Service work (native project.task carrying
        # the FM work type), within the user's companies.
        tdom = [("company_id", "in", companies.ids), ("fm_wo_type", "!=", False)]

        # Optional branch filter (only if fm_branch is installed on both models)
        branches = []
        if "fm.branch" in self.env:
            branches = [
                {"id": b.id, "name": b.name}
                for b in self.env["fm.branch"].sudo().search([("company_id", "in", companies.ids)])
            ]
        if branch_id and "branch_id" in Task._fields:
            tdom += [("branch_id", "=", branch_id)]
            contract_dom += [("branch_id", "=", branch_id)]

        active = Contract.search(contract_dom + [("state", "=", "active")])
        revenue = sum(active.mapped("acv"))

        recent = Task.search(tdom + [("create_date", ">=", since)])

        # SLA proxy: of recent tasks with a deadline that are done (folded stage),
        # the share closed on/before their deadline.
        closed = recent.filtered(lambda t: t.stage_id.fold and t.date_deadline)
        sla_pct = 0.0
        if closed:
            def _on_time(t):
                done = (t.date_last_stage_update or t.write_date)
                return done and done.date() <= t.date_deadline
            met = len(closed.filtered(_on_time))
            sla_pct = round(met / len(closed) * 100, 1)

        open_critical = Task.search_count(
            tdom + [("fm_severity", "in", ("p1_critical", "p2_high")), ("stage_id.fold", "=", False)]
        )

        rated = recent.filtered(lambda t: has_rating and t.rating_last_value) if has_rating else Task
        avg_csat = 0.0
        if rated:
            # Native rating is 0-5; brief CSAT is out of 5.
            avg_csat = round(sum(t.rating_last_value for t in rated) / len(rated), 2)

        # At-risk contracts
        at_risk = active.filtered(lambda c: c.health_band in ("at_risk", "critical"))
        at_risk_rows = [
            {
                "id": c.id,
                "name": c.contract_number,
                "partner": c.partner_id.display_name,
                "score": round(c.health_score, 1),
                "band": c.health_band,
            }
            for c in at_risk.sorted(key=lambda c: c.health_score)[:8]
        ]

        # Top performers (assignee CSAT leaderboard)
        performers = {}
        for t in rated:
            for user in t.user_ids:
                performers.setdefault(user.id, {"name": user.name, "sum": 0.0, "count": 0})
                performers[user.id]["sum"] += t.rating_last_value
                performers[user.id]["count"] += 1
        top_performers = sorted(
            [
                {"name": p["name"], "csat": round(p["sum"] / p["count"], 2), "jobs": p["count"]}
                for p in performers.values()
            ],
            key=lambda p: p["csat"],
            reverse=True,
        )[:6]

        # Service mix (by FM work type)
        mix_labels = dict(Task._fields["fm_wo_type"].selection)
        mix = []
        total_mix = len(recent) or 1
        groups = Task._read_group(tdom + [("create_date", ">=", since)], ["fm_wo_type"], ["__count"])
        for wo_type, count in groups:
            mix.append({
                "label": mix_labels.get(wo_type, wo_type or "Other"),
                "count": count,
                "pct": round(count / total_mix * 100),
            })
        mix.sort(key=lambda m: m["count"], reverse=True)

        return {
            "currency": currency.symbol or currency.name,
            "company_label": "All Companies" if len(companies) > 1 else companies.name,
            "branches": branches,
            "branch_id": branch_id or False,
            "kpis": {
                "revenue": revenue,
                "active_contracts": len(active),
                "sla_compliance": sla_pct,
                "open_critical": open_critical,
                "avg_csat": avg_csat,
            },
            "at_risk": at_risk_rows,
            "top_performers": top_performers,
            "service_mix": mix,
        }
