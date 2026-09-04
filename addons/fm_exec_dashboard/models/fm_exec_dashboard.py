# -*- coding: utf-8 -*-
"""Data provider for the Aabaan executive dashboard.

Three sections, matching the CEO pack the business already works from:
Overview (revenue, cities, sales team, receivables), Expenses (cost structure
and margin) and Cash & Bank (liquidity and movement).

Two rules shape everything below.

**Every figure is read, never invented.** Revenue is posted customer
invoices; expenses are posted spend on expense accounts; cash is the balance
of the bank and cash journals' accounts. Where a number cannot be derived —
a branch with no revenue target, a period with no prior period to compare
against — the payload carries ``False`` and the template shows a dash rather
than a zero, because zero is a claim and a dash is not.

**Chart geometry is computed here, not in the browser.** CLAUDE.md §4
records that OWL dashboards in this repo break on stale asset bundles, so
this module loads no charting library. Bars are CSS percentages; the pie
arcs and the trend polyline are the only real geometry, and both are cheaper
to compute once on the server than on every render.
"""
import math

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Period presets. A "this_*" preset runs to today rather than to the end of
# the calendar period: three weeks of this month measured against a full
# prior month would flatter every result.
PERIOD_PRESETS = [
    ("this_week", "This Week"),
    ("this_month", "This Month"),
    ("this_quarter", "This Quarter"),
    ("this_year", "This Year"),
    ("last_week", "Last Week"),
    ("last_month", "Last Month"),
    ("last_quarter", "Last Quarter"),
    ("last_year", "Last Year"),
    ("custom", "Custom Range"),
]

# From fm_branding's tokens. Ordered so adjacent series stay distinguishable
# when a chart uses only the first two or three.
SERIES_COLORS = [
    "#EE7A22",  # highlight
    "#1C2B3A",  # accent
    "#3D7E8B",  # plumbing
    "#A05E5E",  # pest
    "#6B5B95",  # cleaning
    "#2C5F7C",  # hvac
    "#C18A33",  # warning
    "#2E7D5F",  # positive
]

AGING_BUCKETS = [
    ("current", "Not yet due"),
    ("d1_30", "1 – 30 days"),
    ("d31_60", "31 – 60 days"),
    ("d61_90", "61 – 90 days"),
    ("d90p", "Over 90 days"),
]


class FmExecDashboard(models.AbstractModel):
    """Read-only aggregation over native records, scoped to the user's
    companies. Guarded throughout so the dashboard degrades rather than
    crashes when an optional field or module is absent."""

    _name = "fm.exec.dashboard"
    _description = "Aabaan Executive Dashboard Data"

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    @api.model
    def _check_dashboard_access(self):
        """Enforce the dashboard's group boundary on the server.

        The menu's ``groups=`` only hides the entry point in the UI. This
        method is a public ``@api.model`` reachable over RPC by any
        authenticated user, and the aggregation below runs under ``sudo()``,
        so without this check the ACLs and record rules are bypassed.
        """
        if not self.env.user.has_group("fm_branding.group_fm_account_manager"):
            raise AccessError(
                _("Only FM Account Managers can read the executive dashboard."))

    # ------------------------------------------------------------------
    # Period resolution
    # ------------------------------------------------------------------
    @api.model
    def _resolve_period(self, preset, date_from, date_to):
        """Turn a preset (or an explicit range) into (from, to) dates."""
        today = fields.Date.context_today(self)
        if preset == "custom" and date_from and date_to:
            start = fields.Date.to_date(date_from)
            end = fields.Date.to_date(date_to)
            return (start, end) if start <= end else (end, start)

        if preset == "this_week":
            return today - relativedelta(days=today.weekday()), today
        if preset == "this_month":
            return today.replace(day=1), today
        if preset == "this_quarter":
            return today.replace(month=3 * ((today.month - 1) // 3) + 1, day=1), today
        if preset == "this_year":
            return today.replace(month=1, day=1), today
        if preset == "last_week":
            this_week = today - relativedelta(days=today.weekday())
            return this_week - relativedelta(days=7), this_week - relativedelta(days=1)
        if preset == "last_month":
            this_month = today.replace(day=1)
            return this_month - relativedelta(months=1), this_month - relativedelta(days=1)
        if preset == "last_quarter":
            this_q = today.replace(month=3 * ((today.month - 1) // 3) + 1, day=1)
            return this_q - relativedelta(months=3), this_q - relativedelta(days=1)
        if preset == "last_year":
            this_year = today.replace(month=1, day=1)
            return this_year - relativedelta(years=1), this_year - relativedelta(days=1)
        # Unknown preset — this month, the safest default for a daily read.
        return today.replace(day=1), today

    @staticmethod
    def _prior_period(start, end):
        """The window of equal length ending the day before ``start``."""
        span = (end - start).days
        prior_end = start - relativedelta(days=1)
        return prior_end - relativedelta(days=span), prior_end

    @staticmethod
    def _delta_pct(current, prior):
        """Percentage change, or False when there is nothing to compare to.

        False rather than 0.0: "no prior data" and "flat" are different
        statements, and the template renders them differently.
        """
        if not prior:
            return False
        return round((current - prior) / abs(prior) * 100, 1)

    @staticmethod
    def _months_between(start, end):
        """First day of each month the window touches, oldest first."""
        months, cursor = [], start.replace(day=1)
        last = end.replace(day=1)
        while cursor <= last:
            months.append(cursor)
            cursor += relativedelta(months=1)
        return months

    # ------------------------------------------------------------------
    # Shared query helpers
    # ------------------------------------------------------------------
    def _company_ids(self):
        return self.env.companies.ids

    def _move_has_branch(self):
        return "branch_id" in self.env["account.move"]._fields

    def _invoice_domain(self, start, end, branch_id):
        dom = [
            ("company_id", "in", self._company_ids()),
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
            ("invoice_date", ">=", start),
            ("invoice_date", "<=", end),
        ]
        if branch_id and self._move_has_branch():
            dom.append(("branch_id", "=", branch_id))
        return dom

    def _revenue(self, start, end, branch_id):
        moves = self.env["account.move"].sudo().search(
            self._invoice_domain(start, end, branch_id))
        return sum(moves.mapped("amount_untaxed_signed"))

    def _expense_line_domain(self, start, end, branch_id):
        """Spend booked to an expense account, whatever brought it there.

        Account type rather than move type, so a payroll journal entry and a
        vendor bill both count. In Odoo 19 the ``expense`` prefix covers
        expense, expense_depreciation and expense_direct_cost.
        """
        dom = [
            ("company_id", "in", self._company_ids()),
            ("parent_state", "=", "posted"),
            ("date", ">=", start), ("date", "<=", end),
            ("account_id.account_type", "like", "expense"),
        ]
        if branch_id and self._move_has_branch():
            dom.append(("move_id.branch_id", "=", branch_id))
        return dom

    def _expenses(self, start, end, branch_id):
        lines = self.env["account.move.line"].sudo().search(
            self._expense_line_domain(start, end, branch_id))
        return sum(lines.mapped("balance"))

    def _receivable_line_domain(self, branch_id):
        dom = [
            ("company_id", "in", self._company_ids()),
            ("account_id.account_type", "=", "asset_receivable"),
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
        ]
        if branch_id and self._move_has_branch():
            dom.append(("move_id.branch_id", "=", branch_id))
        return dom

    # ------------------------------------------------------------------
    # Chart geometry
    # ------------------------------------------------------------------
    @staticmethod
    def _pie_slices(rows, radius=100):
        """SVG arc paths for a pie, from [{'label', 'value'}] rows."""
        total = sum(r["value"] for r in rows) or 0
        if not total:
            return []
        slices, angle = [], -math.pi / 2  # start at twelve o'clock
        for i, row in enumerate(rows):
            frac = row["value"] / total
            sweep = frac * 2 * math.pi
            x1, y1 = radius * math.cos(angle), radius * math.sin(angle)
            angle += sweep
            x2, y2 = radius * math.cos(angle), radius * math.sin(angle)
            slices.append({
                "label": row["label"],
                "value": row["value"],
                "pct": round(frac * 100, 1),
                "color": SERIES_COLORS[i % len(SERIES_COLORS)],
                "path": "M 0 0 L %.2f %.2f A %d %d 0 %d 1 %.2f %.2f Z" % (
                    x1, y1, radius, radius, 1 if sweep > math.pi else 0, x2, y2),
            })
        return slices

    @staticmethod
    def _line_points(values, width=560, height=150, pad=8):
        """Polyline points for a trend line, scaled to the series' own max."""
        if not values:
            return ""
        top = max(values) or 1
        step = width / max(len(values) - 1, 1)
        return " ".join(
            "%.1f,%.1f" % (i * step, height - pad - (v / top) * (height - 2 * pad))
            for i, v in enumerate(values)
        )

    @staticmethod
    def _scale_pct(rows, key="value"):
        """Give each row a 0-100 width against the largest row."""
        top = max([abs(r[key]) for r in rows], default=0)
        for r in rows:
            r["pct"] = round(abs(r[key]) / top * 100) if top else 0
        return rows

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    @api.model
    def get_exec_data(self, preset="this_month", date_from=None, date_to=None,
                      branch_id=None):
        self._check_dashboard_access()
        start, end = self._resolve_period(preset, date_from, date_to)
        prior_start, prior_end = self._prior_period(start, end)
        company = self.env.company
        currency = company.currency_id

        branches = self.env["fm.branch"].sudo().search(
            [("company_id", "in", self._company_ids())])

        return {
            "period": {
                "preset": preset,
                "presets": [{"key": k, "label": lbl} for k, lbl in PERIOD_PRESETS],
                "date_from": fields.Date.to_string(start),
                "date_to": fields.Date.to_string(end),
                "prior_from": fields.Date.to_string(prior_start),
                "prior_to": fields.Date.to_string(prior_end),
                "days": (end - start).days + 1,
            },
            "currency": currency.symbol or currency.name,
            "company_label": (
                "All Companies" if len(self.env.companies) > 1 else company.name),
            "branches": [{"id": b.id, "name": b.name} for b in branches],
            "branch_id": branch_id or False,
            "branch_tagging": self._move_has_branch(),
            "overview": self._section_overview(
                start, end, prior_start, prior_end, branch_id, branches),
            "expenses": self._section_expenses(
                start, end, prior_start, prior_end, branch_id, branches),
            "cash": self._section_cash(start, end),
        }

    # ------------------------------------------------------------------
    # 1 · Overview
    # ------------------------------------------------------------------
    def _section_overview(self, start, end, prior_start, prior_end, branch_id,
                          branches):
        Task = self.env["project.task"].sudo()
        Partner = self.env["res.partner"].sudo()

        revenue = self._revenue(start, end, branch_id)
        prior_revenue = self._revenue(prior_start, prior_end, branch_id)

        task_dom = [("company_id", "in", self._company_ids()),
                    ("fm_wo_type", "!=", False)]
        if branch_id and "branch_id" in Task._fields:
            task_dom.append(("branch_id", "=", branch_id))

        jobs = self._jobs_done(task_dom, start, end)
        prior_jobs = self._jobs_done(task_dom, prior_start, prior_end)

        new_clients = self._new_clients(start, end)
        prior_clients = self._new_clients(prior_start, prior_end)

        receivables, overdue = self._receivables(branch_id)
        target = self._target(start, end, branch_id, branches)

        return {
            "kpis": {
                "revenue": revenue,
                "revenue_delta": self._delta_pct(revenue, prior_revenue),
                "target": target,
                "target_achv": round(revenue / target * 100, 1) if target else False,
                "jobs": jobs,
                "jobs_delta": self._delta_pct(jobs, prior_jobs),
                "new_clients": new_clients,
                "clients_delta": self._delta_pct(new_clients, prior_clients),
                "receivables": receivables,
                "overdue": overdue,
                "branch_count": len(branches),
                "team_count": self._team_count(branch_id),
            },
            "cities": self._city_rows(start, end, branch_id, branches),
            "revenue_trend": self._revenue_trend(start, end, branches, branch_id),
            "service_mix": self._service_mix(start, end, branch_id),
            "sales_team": self._sales_team(start, end, branch_id),
            "aging": self._aging(branch_id),
            "job_status": self._job_status(task_dom, end),
            "accounts": self._key_accounts(branch_id),
        }

    def _jobs_done(self, task_dom, start, end):
        return self.env["project.task"].sudo().search_count(task_dom + [
            ("stage_id.fold", "=", True),
            ("date_last_stage_update", ">=", fields.Datetime.to_datetime(start)),
            ("date_last_stage_update", "<", fields.Datetime.to_datetime(
                end + relativedelta(days=1))),
        ])

    def _new_clients(self, start, end):
        return self.env["res.partner"].sudo().search_count([
            ("customer_rank", ">", 0),
            ("create_date", ">=", fields.Datetime.to_datetime(start)),
            ("create_date", "<", fields.Datetime.to_datetime(
                end + relativedelta(days=1))),
        ])

    def _team_count(self, branch_id):
        if "hr.employee" not in self.env:
            return False
        Emp = self.env["hr.employee"].sudo()
        dom = [("company_id", "in", self._company_ids())]
        if branch_id and "fm_branch_id" in Emp._fields:
            dom.append(("fm_branch_id", "=", branch_id))
        return Emp.search_count(dom)

    def _target(self, start, end, branch_id, branches):
        """Pro-rate the monthly branch targets across the period's days."""
        if not branches or "monthly_revenue_target" not in branches._fields:
            return False
        scope = branches.filtered(lambda b: b.id == branch_id) if branch_id else branches
        monthly = sum(scope.mapped("monthly_revenue_target"))
        if not monthly:
            return False
        return monthly * ((end - start).days + 1) / 30.0

    def _receivables(self, branch_id):
        """Open customer balance, and how much of it is past its due date."""
        lines = self.env["account.move.line"].sudo().search(
            self._receivable_line_domain(branch_id))
        today = fields.Date.context_today(self)
        total = sum(lines.mapped("amount_residual"))
        overdue = sum(l.amount_residual for l in lines
                      if l.date_maturity and l.date_maturity < today)
        return total, overdue

    def _city_rows(self, start, end, branch_id, branches):
        """The City & Team table: one row per branch."""
        Task = self.env["project.task"].sudo()
        has_move_branch = self._move_has_branch()
        has_target = branches and "monthly_revenue_target" in branches._fields
        has_task_branch = "branch_id" in Task._fields
        days = (end - start).days + 1
        rows = []
        for b in branches:
            if branch_id and b.id != branch_id:
                continue
            revenue = self._revenue(start, end, b.id) if has_move_branch else False
            target = (b.monthly_revenue_target * days / 30.0) \
                if has_target and b.monthly_revenue_target else False
            receivables, overdue = self._receivables(b.id) if has_move_branch \
                else (False, False)
            jobs = self._jobs_done(
                [("company_id", "in", self._company_ids()),
                 ("fm_wo_type", "!=", False), ("branch_id", "=", b.id)],
                start, end) if has_task_branch else False
            rows.append({
                "id": b.id,
                "city": b.name,
                "manager": b.manager_id.display_name or "—",
                "revenue": revenue,
                "target": target,
                "achv": round(revenue / target * 100) if target and revenue else False,
                "jobs": jobs,
                "receivables": receivables,
                "overdue": overdue,
            })
        rows.sort(key=lambda r: r["revenue"] or 0, reverse=True)
        return rows

    def _revenue_trend(self, start, end, branches, branch_id):
        """Monthly revenue, stacked by branch."""
        months = self._months_between(start, end)
        has_move_branch = self._move_has_branch()
        scope = branches.filtered(lambda b: b.id == branch_id) if branch_id else branches
        series = []
        for i, b in enumerate(scope):
            values = []
            for m in months:
                m_start = max(m, start)
                m_end = min(m + relativedelta(months=1, days=-1), end)
                values.append(self._revenue(m_start, m_end, b.id)
                              if has_move_branch else 0.0)
            if any(values):
                series.append({
                    "label": b.name,
                    "color": SERIES_COLORS[i % len(SERIES_COLORS)],
                    "values": values,
                })
        totals = [sum(s["values"][i] for s in series) for i in range(len(months))]
        return {
            "months": [m.strftime("%b %y") for m in months],
            "series": series,
            "totals": totals,
            "max": max(totals) if totals else 0,
        }

    def _service_mix(self, start, end, branch_id):
        """Revenue split by the service line of the contract behind each
        invoice. Invoices with no contract behind them group as Other rather
        than being dropped, so the slices still sum to revenue."""
        Contract = self.env.get("fm.contract")
        moves = self.env["account.move"].sudo().search(
            self._invoice_domain(start, end, branch_id))
        selection = dict(Contract._fields["service_line"].selection) if Contract is not None else {}
        line_has_sale = "sale_line_ids" in self.env["account.move.line"]._fields
        totals = {}
        for move in moves:
            key = "other"
            if line_has_sale and Contract is not None:
                orders = move.invoice_line_ids.sale_line_ids.order_id
                if orders:
                    contract = Contract.sudo().search(
                        [("sale_order_id", "in", orders.ids)], limit=1)
                    if contract:
                        key = contract.service_line or "other"
            totals[key] = totals.get(key, 0.0) + move.amount_untaxed_signed
        rows = [{"label": selection.get(k, "Other"), "value": v}
                for k, v in sorted(totals.items(), key=lambda kv: -kv[1]) if v > 0]
        return {"rows": rows, "slices": self._pie_slices(rows)}

    def _sales_team(self, start, end, branch_id):
        """Revenue invoiced per salesperson.

        No "vs target" column: no per-salesperson target exists anywhere in
        the database, and inventing one would be worse than leaving it out.
        """
        moves = self.env["account.move"].sudo().search(
            self._invoice_domain(start, end, branch_id))
        per_user = {}
        for move in moves:
            user = move.invoice_user_id if "invoice_user_id" in move._fields else move.user_id
            name = user.display_name if user else _("Unassigned")
            entry = per_user.setdefault(name, {"label": name, "value": 0.0, "count": 0})
            entry["value"] += move.amount_untaxed_signed
            entry["count"] += 1
        rows = sorted(per_user.values(), key=lambda r: -r["value"])[:8]
        return self._scale_pct(rows)

    def _aging(self, branch_id):
        """Open receivables bucketed by how far past due they are."""
        lines = self.env["account.move.line"].sudo().search(
            self._receivable_line_domain(branch_id))
        today = fields.Date.context_today(self)
        buckets = {key: 0.0 for key, _lbl in AGING_BUCKETS}
        for line in lines:
            due = line.date_maturity or line.date
            days = (today - due).days if due else 0
            if days <= 0:
                key = "current"
            elif days <= 30:
                key = "d1_30"
            elif days <= 60:
                key = "d31_60"
            elif days <= 90:
                key = "d61_90"
            else:
                key = "d90p"
            buckets[key] += line.amount_residual
        rows = [{
            "key": key,
            "label": label,
            "value": buckets[key],
            "color": SERIES_COLORS[i % len(SERIES_COLORS)],
        } for i, (key, label) in enumerate(AGING_BUCKETS)]
        return self._scale_pct(rows)

    def _job_status(self, task_dom, end):
        """Every job raised up to the period end, split by stage."""
        groups = self.env["project.task"].sudo()._read_group(
            task_dom + [("create_date", "<", fields.Datetime.to_datetime(
                end + relativedelta(days=1)))],
            ["stage_id"], ["__count"])
        rows = [{"label": stage.name or _("No stage"), "value": count}
                for stage, count in groups if count]
        rows.sort(key=lambda r: -r["value"])
        return {"rows": rows, "slices": self._pie_slices(rows)}

    def _key_accounts(self, branch_id):
        """Largest open customer balances — who to chase first."""
        Move = self.env["account.move"].sudo()
        dom = [
            ("company_id", "in", self._company_ids()),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")),
        ]
        if branch_id and self._move_has_branch():
            dom.append(("branch_id", "=", branch_id))
        today = fields.Date.context_today(self)
        rows = []
        for move in Move.search(dom, order="amount_residual desc", limit=8):
            due = move.invoice_date_due
            rows.append({
                "partner": move.partner_id.display_name,
                "ref": move.name,
                "branch": move.branch_id.name if self._move_has_branch() and move.branch_id else "—",
                "value": move.amount_residual,
                "status": "overdue" if due and due < today else (
                    "partial" if move.payment_state == "partial" else "open"),
                "due": fields.Date.to_string(due) if due else "—",
            })
        return rows

    # ------------------------------------------------------------------
    # 2 · Expenses
    # ------------------------------------------------------------------
    def _section_expenses(self, start, end, prior_start, prior_end, branch_id,
                          branches):
        revenue = self._revenue(start, end, branch_id)
        expenses = self._expenses(start, end, branch_id)
        prior_expenses = self._expenses(prior_start, prior_end, branch_id)
        profit = revenue - expenses

        categories = self._expense_categories(
            start, end, prior_start, prior_end, branch_id, revenue)
        payroll = sum(
            c["value"] for c in categories
            if any(word in c["label"].lower()
                   for word in ("payroll", "wage", "salar", "staff cost")))

        months = self._months_between(start, end)
        rev_series, exp_series = [], []
        for m in months:
            m_start = max(m, start)
            m_end = min(m + relativedelta(months=1, days=-1), end)
            rev_series.append(self._revenue(m_start, m_end, branch_id))
            exp_series.append(self._expenses(m_start, m_end, branch_id))

        pie_rows = [{"label": c["label"], "value": c["value"]}
                    for c in categories[:8] if c["value"] > 0]

        return {
            "kpis": {
                "revenue": revenue,
                "expenses": expenses,
                "expenses_delta": self._delta_pct(expenses, prior_expenses),
                "profit": profit,
                "margin": round(profit / revenue * 100, 1) if revenue else False,
                "payroll_share": round(payroll / expenses * 100) if expenses else False,
            },
            "trend": {
                "months": [m.strftime("%b %y") for m in months],
                "revenue": rev_series,
                "expenses": exp_series,
                "max": max(rev_series + exp_series) if (rev_series or exp_series) else 0,
                "revenue_points": self._line_points(rev_series),
            },
            "categories": categories,
            "category_slices": self._pie_slices(pie_rows),
            "by_city": self._expenses_by_city(start, end, branches, branch_id),
        }

    def _expense_categories(self, start, end, prior_start, prior_end, branch_id,
                            revenue):
        """Spend grouped by the expense account it was booked to.

        The account is the category: §7 of the finance requirements asks for
        Branch → Department → Expense Category, and the chart of accounts is
        where that category already lives. No parallel taxonomy to maintain.
        """
        Line = self.env["account.move.line"].sudo()

        def spend(a, b):
            totals = {}
            for account, balance in Line._read_group(
                    self._expense_line_domain(a, b, branch_id),
                    ["account_id"], ["balance:sum"]):
                if balance:
                    totals[account] = balance
            return totals

        current = spend(start, end)
        prior = spend(prior_start, prior_end)
        total = sum(current.values()) or 0
        rows = []
        for i, (account, value) in enumerate(
                sorted(current.items(), key=lambda kv: -kv[1])):
            rows.append({
                "label": account.name,
                "code": account.code or "—",
                "value": value,
                "share": round(value / total * 100, 1) if total else 0,
                "of_revenue": round(value / revenue * 100, 1) if revenue else False,
                "delta": self._delta_pct(value, prior.get(account, 0.0)),
                "color": SERIES_COLORS[i % len(SERIES_COLORS)],
            })
        return self._scale_pct(rows)

    def _expenses_by_city(self, start, end, branches, branch_id):
        """Cost per branch.

        Only spend on a document that names its branch can be attributed. The
        rest is reported as unallocated rather than spread on an assumption —
        an allocation rule for shared overheads is a management decision, not
        something a dashboard should invent.
        """
        if not self._move_has_branch():
            return {"rows": [], "unallocated": False}
        total = self._expenses(start, end, None)
        scope = branches.filtered(lambda b: b.id == branch_id) if branch_id else branches
        rows, allocated = [], 0.0
        for i, b in enumerate(scope):
            value = self._expenses(start, end, b.id)
            allocated += value
            rows.append({
                "label": b.name,
                "value": value,
                "color": SERIES_COLORS[i % len(SERIES_COLORS)],
            })
        rows.sort(key=lambda r: -r["value"])
        return {
            "rows": self._scale_pct(rows),
            "unallocated": (total - allocated) if not branch_id else False,
        }

    # ------------------------------------------------------------------
    # 3 · Cash & Bank
    # ------------------------------------------------------------------
    def _section_cash(self, start, end):
        """Cash is not branch-scoped: a bank account belongs to the company,
        not to an emirate, so the branch filter deliberately does not apply
        here. Splitting a shared account between branches would be a made-up
        number."""
        Journal = self.env["account.journal"].sudo()
        Line = self.env["account.move.line"].sudo()
        journals = Journal.search([
            ("company_id", "in", self._company_ids()),
            ("type", "in", ("bank", "cash")),
        ])
        type_labels = dict(Journal._fields["type"].selection)

        accounts, total_cash = [], 0.0
        for i, journal in enumerate(journals):
            account = journal.default_account_id
            if not account:
                continue
            balance = sum(Line.search([
                ("account_id", "=", account.id),
                ("parent_state", "=", "posted"),
                ("date", "<=", end),
            ]).mapped("balance"))
            total_cash += balance
            accounts.append({
                "name": journal.name,
                "type": type_labels.get(journal.type, journal.type),
                "number": self._masked_account_number(journal),
                "balance": balance,
                "color": SERIES_COLORS[i % len(SERIES_COLORS)],
            })
        self._scale_pct(accounts, key="balance")

        account_ids = journals.mapped("default_account_id").ids
        inflow, outflow = self._cash_movement(account_ids, start, end)

        months = self._months_between(start, end)
        m_in, m_out, running, balance = [], [], [], 0.0
        for m in months:
            m_start = max(m, start)
            m_end = min(m + relativedelta(months=1, days=-1), end)
            i_, o_ = self._cash_movement(account_ids, m_start, m_end)
            m_in.append(i_)
            m_out.append(o_)
            balance += i_ - o_
            running.append(balance)

        return {
            "kpis": {
                "total_cash": total_cash,
                "account_count": len(accounts),
                "inflow": inflow,
                "outflow": outflow,
                "net": inflow - outflow,
            },
            "accounts": accounts,
            "flow": {
                "months": [m.strftime("%b %y") for m in months],
                "inflow": m_in,
                "outflow": m_out,
                "max": max(m_in + m_out) if (m_in or m_out) else 0,
                "running": running,
                "running_points": self._line_points([v - min(running + [0]) for v in running]),
            },
            "transactions": self._recent_transactions(account_ids, end),
        }

    @staticmethod
    def _masked_account_number(journal):
        """Last four digits only — a dashboard is a shared screen."""
        number = journal.bank_acc_number if "bank_acc_number" in journal._fields else None
        if not number:
            return _("Petty cash") if journal.type == "cash" else "—"
        digits = "".join(ch for ch in number if ch.isdigit())
        return "•••• %s" % digits[-4:] if len(digits) >= 4 else "••••"

    def _cash_movement(self, account_ids, start, end):
        """Money into and out of the cash and bank accounts."""
        if not account_ids:
            return 0.0, 0.0
        lines = self.env["account.move.line"].sudo().search([
            ("account_id", "in", account_ids),
            ("parent_state", "=", "posted"),
            ("date", ">=", start), ("date", "<=", end),
        ])
        return sum(lines.mapped("debit")), sum(lines.mapped("credit"))

    def _recent_transactions(self, account_ids, end):
        if not account_ids:
            return []
        lines = self.env["account.move.line"].sudo().search([
            ("account_id", "in", account_ids),
            ("parent_state", "=", "posted"),
            ("date", "<=", end),
        ], order="date desc, id desc", limit=10)
        return [{
            "date": fields.Date.to_string(l.date),
            "account": l.account_id.name,
            "label": l.move_id.ref or l.name or l.move_id.name,
            "amount": l.debit - l.credit,
            "partner": l.partner_id.display_name or "—",
        } for l in lines]
