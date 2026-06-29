from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AabaanCeoDashboard(models.AbstractModel):
    """Data provider for the CEO Command Centre OWL dashboard.

    Read-only aggregation over contracts, visits and posted accounting
    entries. Scoped to the companies the user is allowed to see
    (``self.env.companies``), so it works as a consolidated group view.
    """

    _name = "aabaan.ceo.dashboard"
    _description = "Aabaan CEO Command Centre Data"

    # ------------------------------------------------------------------
    # Public entry point (called from the OWL client action via ORM)
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, period="ytd"):
        companies = self.env.companies
        currency = self.env.company.currency_id
        today = fields.Date.context_today(self)
        start = self._period_start(today, period)

        financials = self._financials(companies, start, today)
        operations = self._operations(companies, today)

        return {
            "user_name": self.env.user.name,
            "company_label": self._company_label(companies),
            "company_count": len(companies),
            "period_label": dict(self._period_selection()).get(period, "Year to Date"),
            "currency": {
                "symbol": currency.symbol or currency.name,
                "name": currency.name,
                "position": currency.position,
            },
            "kpis": financials["kpis"],
            "operations": operations["stats"],
            "activity": operations["activity"],
            "alerts": self._alerts(financials, operations, currency),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _period_selection(self):
        return [
            ("ytd", "Year to Date"),
            ("mtd", "Month to Date"),
            ("qtd", "Quarter to Date"),
            ("last_year", "Last 12 Months"),
        ]

    def _period_start(self, today, period):
        if period == "mtd":
            return today.replace(day=1)
        if period == "qtd":
            quarter_month = ((today.month - 1) // 3) * 3 + 1
            return date(today.year, quarter_month, 1)
        if period == "last_year":
            return today - relativedelta(years=1)
        return date(today.year, 1, 1)  # ytd

    def _company_label(self, companies):
        if len(companies) == 1:
            return companies.name
        return "All Companies"

    # ------------------------------------------------------------------
    # Financial KPIs from posted account.move entries
    # ------------------------------------------------------------------
    def _financials(self, companies, start, today):
        Move = self.env["account.move"]
        company_domain = [("company_id", "in", companies.ids)]

        # Sales (posted customer invoices/credit notes in the period)
        sales_domain = company_domain + [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
            ("invoice_date", ">=", start),
            ("invoice_date", "<=", today),
        ]
        sales_ytd = self._sum(Move, sales_domain, "amount_total_signed")

        # Receivables (open customer balance, all time)
        recv_domain = company_domain + [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
        ]
        receivables = self._sum(Move, recv_domain, "amount_residual_signed")
        overdue_recv = self._sum(
            Move,
            recv_domain + [("invoice_date_due", "<", today)],
            "amount_residual_signed",
        )

        # Payables (open vendor balance, all time)
        pay_domain = company_domain + [
            ("move_type", "in", ["in_invoice", "in_refund"]),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
        ]
        payables = abs(self._sum(Move, pay_domain, "amount_residual_signed"))

        # Cash position (balance of liquidity accounts on posted entries)
        cash = self._cash_position(companies)

        kpis = {
            "sales_ytd": sales_ytd,
            "receivables": receivables,
            "overdue_receivables": overdue_recv,
            "payables": payables,
            "cash_position": cash,
        }
        return {"kpis": kpis}

    def _sum(self, model, domain, field):
        # Aggregate via sudo so the dashboard works for CEO users who only
        # have read access to the scheduler models; figures stay read-only.
        result = model.sudo()._read_group(domain, [], [f"{field}:sum"])
        if result and result[0][0] is not None:
            return result[0][0]
        return 0.0

    def _cash_position(self, companies):
        Line = self.env["account.move.line"].sudo()
        domain = [
            ("company_id", "in", companies.ids),
            ("parent_state", "=", "posted"),
            ("account_id.account_type", "=", "asset_cash"),
        ]
        result = Line._read_group(domain, [], ["balance:sum"])
        if result and result[0][0] is not None:
            return result[0][0]
        return 0.0

    # ------------------------------------------------------------------
    # Operational stats from contracts and visits
    # ------------------------------------------------------------------
    def _operations(self, companies, today):
        Contract = self.env["aabaan.service.contract"]
        Visit = self.env["aabaan.service.visit"]
        company_domain = [("company_id", "in", companies.ids)]
        soon = today + relativedelta(days=30)
        month_start = today.replace(day=1)

        active_contracts = Contract.search_count(company_domain + [("state", "=", "active")])
        expiring = Contract.search_count(
            company_domain
            + [("state", "=", "active"), ("end_date", ">=", today), ("end_date", "<=", soon)]
        )
        pending_approvals = Visit.search_count(
            company_domain + [("state", "=", "done"), ("approved", "=", False)]
        )
        visits_today = Visit.search_count(company_domain + [("planned_date", "=", today)])
        missed_month = Visit.search_count(
            company_domain + [("state", "=", "missed"), ("planned_date", ">=", month_start)]
        )

        # Activity timeline: most recently touched contracts
        recent = Contract.search(company_domain, order="write_date desc", limit=8)
        activity = [
            {
                "id": c.id,
                "name": c.name,
                "partner": c.partner_id.display_name,
                "value": c.contract_value,
                "currency": c.currency_id.symbol or c.currency_id.name,
                "state": dict(c._fields["state"].selection).get(c.state, c.state),
                "since": self._humanize(c.write_date, today),
            }
            for c in recent
        ]

        return {
            "stats": {
                "active_contracts": active_contracts,
                "expiring_contracts": expiring,
                "pending_approvals": pending_approvals,
                "visits_today": visits_today,
                "missed_this_month": missed_month,
            },
            "activity": activity,
        }

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
        months = days // 30
        return "%smo ago" % months

    # ------------------------------------------------------------------
    # Alert feed
    # ------------------------------------------------------------------
    def _alerts(self, financials, operations, currency):
        alerts = []
        kpis = financials["kpis"]
        stats = operations["stats"]
        sym = currency.symbol or currency.name

        if kpis["overdue_receivables"]:
            alerts.append({
                "level": "danger",
                "text": "Overdue receivables: %s %s past due — chase to free up cash"
                % (sym, "{:,.0f}".format(kpis["overdue_receivables"])),
            })
        if stats["pending_approvals"]:
            alerts.append({
                "level": "warning",
                "text": "%s completed visit(s) awaiting your approval"
                % stats["pending_approvals"],
            })
        if stats["expiring_contracts"]:
            alerts.append({
                "level": "warning",
                "text": "%s active contract(s) expiring within 30 days — plan renewals"
                % stats["expiring_contracts"],
            })
        if stats["missed_this_month"]:
            alerts.append({
                "level": "danger",
                "text": "%s visit(s) marked missed this month — review with supervisors"
                % stats["missed_this_month"],
            })
        if not alerts:
            alerts.append({
                "level": "ok",
                "text": "All clear — no overdue receivables, approvals or missed visits.",
            })
        return alerts
