# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class FmDashboardExec(models.AbstractModel):
    """Data provider for the Executive Dashboard OWL client action (brief §7.1).
    Read-only aggregation over contracts and work orders, scoped to the user's
    allowed companies.
    """

    _name = "fm.dashboard.exec"
    _description = "FM Executive Dashboard Data"

    @api.model
    def get_dashboard_data(self):
        companies = self.env.companies
        currency = self.env.company.currency_id
        today = fields.Date.context_today(self)
        since = fields.Datetime.to_datetime(today - relativedelta(days=90))
        Contract = self.env["fm.contract"].sudo()
        Wo = self.env["fm.workorder"].sudo()
        cdom = [("company_id", "in", companies.ids)]
        # fm.contract company is delegated through the sale order
        contract_dom = [("sale_order_id.company_id", "in", companies.ids)]

        active = Contract.search(contract_dom + [("state", "=", "active")])
        revenue = sum(active.mapped("acv"))

        recent_wos = Wo.search(cdom + [("create_date", ">=", since)])
        evaluated = recent_wos.filtered(lambda w: w.sla_resolution_status in ("met", "breached"))
        sla_pct = 0.0
        if evaluated:
            met = len(evaluated.filtered(lambda w: w.sla_resolution_status == "met"))
            sla_pct = round(met / len(evaluated) * 100, 1)

        open_critical = Wo.search_count(
            cdom + [("severity", "in", ("p1_critical", "p2_high")), ("stage", "not in", ("signed_off", "cancelled"))]
        )
        rated = recent_wos.filtered(lambda w: w.csat_rating)
        avg_csat = round(sum(int(w.csat_rating) for w in rated) / len(rated), 2) if rated else 0.0

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

        # Top performers (technician CSAT leaderboard)
        performers = {}
        for wo in rated:
            tech = wo.technician_id
            if not tech:
                continue
            performers.setdefault(tech.id, {"name": tech.name, "sum": 0, "count": 0})
            performers[tech.id]["sum"] += int(wo.csat_rating)
            performers[tech.id]["count"] += 1
        top_performers = sorted(
            [
                {"name": p["name"], "csat": round(p["sum"] / p["count"], 2), "jobs": p["count"]}
                for p in performers.values()
            ],
            key=lambda p: p["csat"],
            reverse=True,
        )[:6]

        # Service mix (by WO type)
        mix_labels = dict(Wo._fields["wo_type"].selection)
        mix = []
        total_mix = len(recent_wos) or 1
        groups = Wo._read_group(cdom + [("create_date", ">=", since)], ["wo_type"], ["__count"])
        for wo_type, count in groups:
            mix.append({
                "label": mix_labels.get(wo_type, wo_type),
                "count": count,
                "pct": round(count / total_mix * 100),
            })
        mix.sort(key=lambda m: m["count"], reverse=True)

        return {
            "currency": currency.symbol or currency.name,
            "company_label": "All Companies" if len(companies) > 1 else companies.name,
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
