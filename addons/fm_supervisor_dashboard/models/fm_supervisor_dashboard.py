# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import api, fields, models

# Status model shown on the calendar (key, label, colour).
STATUSES = [
    ("planned", "Planned", "#2f6fed"),
    ("in_progress", "In Progress", "#e08a1e"),
    ("done", "Completed", "#1f9d57"),
    ("overdue", "Overdue", "#e23d3d"),
    ("cancelled", "Cancelled", "#9aa2b1"),
]
STATUS_COLOR = {k: c for k, _l, c in STATUSES}


class FmSupervisorDashboard(models.AbstractModel):
    """Data provider for the Supervisor Dashboard — a monthly maintenance
    calendar of visits with status tags, a KPI strip and simple summaries,
    scoped to the user's companies."""

    _name = "fm.supervisor.dashboard"
    _description = "FM Supervisor Dashboard Data"

    @api.model
    def get_board_data(self, month_start=None, technician_id=None, service_line=None, branch_id=None):
        Task = self.env["project.task"].sudo()
        companies = self.env.companies
        today = fields.Date.context_today(self)

        # Anchor month
        anchor = fields.Date.to_date(month_start) if month_start else today.replace(day=1)
        first = anchor.replace(day=1)
        # Grid starts on the Sunday on/before the 1st; always 6 rows (42 cells).
        grid_start = first - timedelta(days=(first.weekday() + 1) % 7)
        grid_days = [grid_start + timedelta(days=i) for i in range(42)]
        grid_end = grid_days[-1]

        dom = [
            ("company_id", "in", companies.ids),
            ("fm_wo_type", "!=", False),
            ("date_deadline", ">=", grid_start),
            ("date_deadline", "<=", grid_end + timedelta(days=1)),
        ]
        if technician_id:
            dom.append(("user_ids", "=", technician_id))
        if service_line:
            dom.append(("fm_service_line", "=", service_line))
        if branch_id and "branch_id" in Task._fields:
            dom.append(("branch_id", "=", branch_id))
        tasks = Task.search(dom)

        def status_of(t):
            name = (t.stage_id.name or "").lower()
            if t.stage_id.fold:
                return "cancelled" if "cancel" in name else "done"
            dd = t.date_deadline.date() if t.date_deadline else False
            if dd and dd < today:
                return "overdue"
            if "progress" in name:
                return "in_progress"
            return "planned"

        by_day = {}
        for t in tasks:
            if not t.date_deadline:
                continue
            key = t.date_deadline.date().isoformat()
            st = status_of(t)
            by_day.setdefault(key, []).append({
                "id": t.id,
                "status": st,
                "status_label": dict((k, l) for k, l, _c in STATUSES).get(st, st),
                "color": STATUS_COLOR.get(st, "#2f6fed"),
                "title": t.partner_id.display_name or t.name,
                "sub": t.fm_asset_id.display_name if t.fm_asset_id else (
                    ", ".join(t.user_ids.mapped("name")) or ""),
                "tech": ", ".join(t.user_ids.mapped("name")) or "Unassigned",
            })
        # sort each day's events by status order
        order = {k: i for i, (k, _l, _c) in enumerate(STATUSES)}
        for v in by_day.values():
            v.sort(key=lambda e: order.get(e["status"], 99))

        weeks = []
        for w in range(6):
            row = []
            for i in range(7):
                d = grid_days[w * 7 + i]
                row.append({
                    "date": d.isoformat(),
                    "day": d.day,
                    "in_month": d.month == first.month,
                    "is_today": d == today,
                    "is_weekend": d.weekday() in (4, 5),  # Fri/Sat (UAE)
                    "events": by_day.get(d.isoformat(), []),
                })
            weeks.append(row)

        # KPIs over the anchored month
        in_month = tasks.filtered(lambda t: t.date_deadline and t.date_deadline.month == first.month
                                  and t.date_deadline.year == first.year)
        open_m = in_month.filtered(lambda t: not t.stage_id.fold)
        m_total = len(in_month)
        m_done = len(in_month.filtered(lambda t: t.stage_id.fold))
        kpis = {
            "today": len(tasks.filtered(lambda t: t.date_deadline and t.date_deadline.date() == today)),
            "overdue": len(open_m.filtered(lambda t: t.date_deadline and t.date_deadline.date() < today)),
            "unassigned": len(open_m.filtered(lambda t: not t.user_ids)),
            "month_total": m_total,
            "done": m_done,
            "completion": round(m_done / m_total * 100) if m_total else 0,
        }

        # Filter option lists
        technicians = [{"id": u.id, "name": u.name} for u in tasks.mapped("user_ids").sorted("name")]
        branches = []
        if "fm.branch" in self.env:
            branches = [{"id": b.id, "name": b.name}
                        for b in self.env["fm.branch"].sudo().search([("company_id", "in", companies.ids)])]
        sl_options = Task.fields_get(["fm_service_line"])["fm_service_line"]["selection"]
        service_lines = [{"key": k, "name": v} for k, v in sl_options]

        prev_m = (first - timedelta(days=1)).replace(day=1)
        next_m = (first + timedelta(days=31)).replace(day=1)
        return {
            "month_label": first.strftime("%B %Y"),
            "month_start": first.isoformat(),
            "prev_month": prev_m.isoformat(),
            "next_month": next_m.isoformat(),
            "this_month": today.replace(day=1).isoformat(),
            "weekdays": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            "weeks": weeks,
            "legend": [{"key": k, "label": l, "color": c} for k, l, c in STATUSES],
            "kpis": kpis,
            "technicians": technicians,
            "branches": branches,
            "service_lines": service_lines,
            "filters": {
                "technician_id": technician_id or False,
                "service_line": service_line or False,
                "branch_id": branch_id or False,
            },
            "company_label": "All Companies" if len(companies) > 1 else self.env.company.name,
        }
