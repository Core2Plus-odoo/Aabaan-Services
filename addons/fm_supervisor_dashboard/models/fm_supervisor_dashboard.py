# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class FmSupervisorDashboard(models.AbstractModel):
    """Data provider for the Supervisor Dashboard — a week board of visits plus
    at-a-glance KPIs, scoped to the user's companies. Everything a supervisor
    needs is on one screen; no drill-down required."""

    _name = "fm.supervisor.dashboard"
    _description = "FM Supervisor Dashboard Data"

    @api.model
    def get_board_data(self, week_start=None, technician_id=None, service_line=None, branch_id=None):
        Task = self.env["project.task"].sudo()
        companies = self.env.companies
        today = fields.Date.context_today(self)

        # Week window (Mon–Sun) around the requested / current week.
        if week_start:
            monday = fields.Date.to_date(week_start)
        else:
            monday = today - timedelta(days=today.weekday())
        days = [monday + timedelta(days=i) for i in range(7)]
        week_end = days[-1]

        dom = [
            ("company_id", "in", companies.ids),
            ("fm_wo_type", "!=", False),
            ("date_deadline", ">=", monday),
            ("date_deadline", "<=", week_end),
        ]
        if technician_id:
            dom.append(("user_ids", "=", technician_id))
        if service_line:
            dom.append(("fm_service_line", "=", service_line))
        has_branch = "branch_id" in Task._fields
        if branch_id and has_branch:
            dom.append(("branch_id", "=", branch_id))

        tasks = Task.search(dom)

        def status_of(t):
            if t.stage_id.fold:
                # folded = signed off / cancelled → treat cancelled separately
                name = (t.stage_id.name or "").lower()
                return "cancelled" if "cancel" in name else "done"
            dd = t.date_deadline.date() if t.date_deadline else False
            if dd and dd < today:
                return "overdue"
            if dd == today:
                return "today"
            return "scheduled"

        by_day = {d.isoformat(): [] for d in days}
        sev_labels = dict(Task._fields["fm_severity"].selection)
        for t in tasks:
            if not t.date_deadline:
                continue
            key = t.date_deadline.date().isoformat()
            if key not in by_day:
                continue
            by_day[key].append({
                "id": t.id,
                "title": t.partner_id.display_name or t.name,
                "asset": t.fm_asset_id.display_name if t.fm_asset_id else "",
                "tech": ", ".join(t.user_ids.mapped("name")) or "Unassigned",
                "status": status_of(t),
                "severity": t.fm_severity or "",
                "severity_label": sev_labels.get(t.fm_severity, ""),
                "service_line": t.fm_service_line or "",
            })

        day_rows = [{
            "date": d.isoformat(),
            "weekday": d.strftime("%a"),
            "day": d.day,
            "month": d.strftime("%b"),
            "is_today": d == today,
            "is_weekend": d.weekday() >= 5,
            "visits": by_day[d.isoformat()],
        } for d in days]

        # KPIs (this week window unless noted)
        open_tasks = tasks.filtered(lambda t: not t.stage_id.fold)
        kpis = {
            "today": len(tasks.filtered(lambda t: t.date_deadline and t.date_deadline.date() == today)),
            "overdue": len(open_tasks.filtered(lambda t: t.date_deadline and t.date_deadline.date() < today)),
            "unassigned": len(open_tasks.filtered(lambda t: not t.user_ids)),
            "week_total": len(tasks),
            "done": len(tasks.filtered(lambda t: t.stage_id.fold)),
        }

        # Filter option lists
        technicians = [
            {"id": u.id, "name": u.name}
            for u in tasks.mapped("user_ids").sorted("name")
        ]
        branches = []
        if "fm.branch" in self.env:
            branches = [
                {"id": b.id, "name": b.name}
                for b in self.env["fm.branch"].sudo().search([("company_id", "in", companies.ids)])
            ]
        # fm_service_line is a related Selection, so resolve its options via
        # fields_get (its .selection attribute is a callable, not a list).
        sl_options = Task.fields_get(["fm_service_line"])["fm_service_line"]["selection"]
        service_lines = [{"key": k, "name": v} for k, v in sl_options]

        return {
            "week_start": monday.isoformat(),
            "week_label": "%s – %s %s" % (
                monday.strftime("%d %b"), week_end.strftime("%d %b"), week_end.strftime("%Y")
            ),
            "prev_week": (monday - timedelta(days=7)).isoformat(),
            "next_week": (monday + timedelta(days=7)).isoformat(),
            "this_week": (today - timedelta(days=today.weekday())).isoformat(),
            "days": day_rows,
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
