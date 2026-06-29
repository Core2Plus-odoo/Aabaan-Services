from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AabaanSupervisorDashboard(models.AbstractModel):
    """Data provider for the Supervisor Command Centre OWL dashboard.

    Operations-focused (no financials): today's workload, approvals,
    visit outcomes, team load and renewals. Scoped to the companies the
    user is allowed to see.
    """

    _name = "aabaan.supervisor.dashboard"
    _description = "Aabaan Supervisor Command Centre Data"

    @api.model
    def get_dashboard_data(self):
        companies = self.env.companies
        today = fields.Date.context_today(self)
        Visit = self.env["aabaan.service.visit"]
        Contract = self.env["aabaan.service.contract"]
        company_domain = [("company_id", "in", companies.ids)]
        week_end = today + relativedelta(days=7)
        month_start = today.replace(day=1)
        soon = today + relativedelta(days=30)

        # ---- Headline KPI counts ----
        visits_today = Visit.search_count(company_domain + [("planned_date", "=", today)])
        in_progress = Visit.search_count(company_domain + [("state", "=", "in_progress")])
        pending_approvals = Visit.search_count(
            company_domain + [("state", "=", "done"), ("approved", "=", False)]
        )
        missed_month = Visit.search_count(
            company_domain + [("state", "=", "missed"), ("planned_date", ">=", month_start)]
        )

        # ---- Secondary stat strip ----
        unscheduled = Visit.search_count(company_domain + [("state", "=", "draft")])
        this_week = Visit.search_count(
            company_domain + [("planned_date", ">=", today), ("planned_date", "<=", week_end)]
        )
        active_contracts = Contract.search_count(company_domain + [("state", "=", "active")])
        expiring = Contract.search_count(
            company_domain
            + [("state", "=", "active"), ("end_date", ">=", today), ("end_date", "<=", soon)]
        )

        # Completion rate this month (done / (done + missed))
        done_month = Visit.search_count(
            company_domain + [("state", "=", "done"), ("planned_date", ">=", month_start)]
        )
        denom = done_month + missed_month
        completion_rate = round((done_month / denom) * 100) if denom else 100

        return {
            "user_name": self.env.user.name,
            "company_label": "All Companies" if len(companies) > 1 else companies.name,
            "company_count": len(companies),
            "kpis": {
                "visits_today": visits_today,
                "in_progress": in_progress,
                "pending_approvals": pending_approvals,
                "missed_this_month": missed_month,
            },
            "stats": {
                "unscheduled": unscheduled,
                "this_week": this_week,
                "active_contracts": active_contracts,
                "expiring_contracts": expiring,
                "completion_rate": completion_rate,
            },
            "team": self._team_load(Visit, company_domain, today, week_end),
            "activity": self._activity(Visit, company_domain, today),
            "alerts": self._alerts(pending_approvals, missed_month, unscheduled, expiring),
        }

    # ------------------------------------------------------------------
    def _team_load(self, Visit, company_domain, today, week_end):
        """Upcoming (today→+7d) open visit count per technician."""
        domain = company_domain + [
            ("planned_date", ">=", today),
            ("planned_date", "<=", week_end),
            ("state", "in", ["draft", "scheduled", "in_progress"]),
        ]
        groups = Visit._read_group(domain, ["technician_ids"], ["__count"])
        rows = []
        for technician, count in groups:
            if technician:
                rows.append({"name": technician.name, "count": count})
        rows.sort(key=lambda r: r["count"], reverse=True)
        return rows[:8]

    def _activity(self, Visit, company_domain, today):
        recent = Visit.search(company_domain, order="write_date desc", limit=8)
        state_labels = dict(Visit._fields["state"].selection)
        data = []
        for v in recent:
            techs = ", ".join(v.technician_ids.mapped("name")) or "Unassigned"
            data.append({
                "id": v.id,
                "name": v.name,
                "partner": v.partner_id.display_name,
                "technician": techs,
                "state": state_labels.get(v.state, v.state),
                "state_key": v.state,
                "since": self._humanize(v.write_date, today),
            })
        return data

    def _humanize(self, when, today):
        if not when:
            return ""
        days = (today - fields.Date.to_date(when)).days
        if days <= 0:
            return "today"
        if days == 1:
            return "1d ago"
        if days < 30:
            return "%sd ago" % days
        return "%smo ago" % (days // 30)

    def _alerts(self, pending_approvals, missed_month, unscheduled, expiring):
        alerts = []
        if pending_approvals:
            alerts.append({
                "level": "warning",
                "text": "%s completed visit(s) waiting for your approval" % pending_approvals,
            })
        if unscheduled:
            alerts.append({
                "level": "warning",
                "text": "%s visit(s) still unscheduled — assign a technician and date" % unscheduled,
            })
        if missed_month:
            alerts.append({
                "level": "danger",
                "text": "%s visit(s) missed this month — follow up and reschedule" % missed_month,
            })
        if expiring:
            alerts.append({
                "level": "warning",
                "text": "%s contract(s) expiring within 30 days" % expiring,
            })
        if not alerts:
            alerts.append({
                "level": "ok",
                "text": "All clear — nothing pending approval, unscheduled or missed.",
            })
        return alerts
