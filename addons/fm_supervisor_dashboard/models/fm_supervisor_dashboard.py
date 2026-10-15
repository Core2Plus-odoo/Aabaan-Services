# -*- coding: utf-8 -*-
import base64
import io
from datetime import date, timedelta

import xlsxwriter
import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

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
    def _check_dashboard_access(self):
        """Enforce the dashboard's group boundary on the server.

        The menu's ``groups=`` only hides the entry point in the UI. This
        method is a public ``@api.model`` reachable over RPC by any
        authenticated user, and the aggregation below runs under ``sudo()``,
        so without this check the ACLs and record rules are bypassed.
        """
        if not self.env.user.has_group("fm_branding.group_fm_dispatcher"):
            raise AccessError(_("Only FM Dispatchers can read the supervisor dashboard."))

    @api.model
    def get_board_data(self, month_start=None, technician_id=None, service_line=None, branch_id=None):
        self._check_dashboard_access()
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

        def closed(t):
            # Completed (green) means the job reached its last stage —
            # Signed Off / Certificate Issued, the folded ones. "Mark as
            # done" only takes a job to Completed, which is not the end.
            return t.state == "1_canceled" or t.stage_id.fold

        def status_of(t):
            name = (t.stage_id.name or "").lower()
            if t.state == "1_canceled":
                return "cancelled"
            if closed(t):
                return "cancelled" if "cancel" in name else "done"
            dd = t.date_deadline.date() if t.date_deadline else False
            if dd and dd < today:
                return "overdue"
            if "progress" in name:
                return "in_progress"
            return "planned"

        def title_of(t):
            # The job's own name ("Customer — Carpet Cleaning (2/4)"), led by
            # the customer when the name does not already carry it, as
            # Odoo's one-task-per-line names do ("S00738 - [CODE] Service").
            customer = t.partner_id.display_name
            name = t.name or ""
            if customer and customer.lower() not in name.lower():
                return "%s — %s" % (customer, name) if name else customer
            return name or customer or ""

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
                "title": title_of(t),
                "sub": t.fm_asset_id.display_name if t.fm_asset_id else (
                    ", ".join(t.user_ids.mapped("name")) or ""),
                "tech": ", ".join(t.user_ids.mapped("name")) or "Unassigned",
            })
        # sort each day's events by status order
        # Finished work first so it is never buried under "+N more", then
        # what needs attention, then what is still ahead.
        order = {k: i for i, k in enumerate(("done", "in_progress", "overdue", "planned", "cancelled"))}
        for v in by_day.values():
            v.sort(key=lambda e: order.get(e["status"], 99))

        weeks = []
        for w in range(6):
            row = []
            for i in range(7):
                d = grid_days[w * 7 + i]
                # Days of the neighbouring months only pad the grid; their
                # visits belong to that month's page, not this one.
                evts = by_day.get(d.isoformat(), []) if d.month == first.month else []
                row.append({
                    "date": d.isoformat(),
                    "day": d.day,
                    "in_month": d.month == first.month,
                    "is_today": d == today,
                    "is_weekend": d.weekday() in (4, 5),  # Fri/Sat (UAE)
                    "events": evts,
                    "more": max(0, len(evts) - 3),
                })
            if any(c["in_month"] for c in row):
                weeks.append(row)

        # KPIs over the anchored month
        in_month = tasks.filtered(lambda t: t.date_deadline and t.date_deadline.month == first.month
                                  and t.date_deadline.year == first.year)
        open_m = in_month.filtered(lambda t: not closed(t))
        today_t = tasks.filtered(lambda t: t.date_deadline and t.date_deadline.date() == today)
        overdue_t = open_m.filtered(lambda t: t.date_deadline and t.date_deadline.date() < today)
        unassigned_t = open_m.filtered(lambda t: not t.user_ids)
        done_t = in_month.filtered(lambda t: status_of(t) == "done")
        m_total = len(in_month)
        m_done = len(done_t)
        kpis = {
            "today": len(today_t),
            "overdue": len(overdue_t),
            "unassigned": len(unassigned_t),
            "month_total": m_total,
            "done": m_done,
            "completion": round(m_done / m_total * 100) if m_total else 0,
        }
        # The records behind each card, so a click opens exactly what was
        # counted rather than a domain that might drift from the count.
        kpi_ids = {
            "today": today_t.ids,
            "overdue": overdue_t.ids,
            "unassigned": unassigned_t.ids,
            "month_total": in_month.ids,
            "done": done_t.ids,
        }

        # Filter option lists
        technicians = [{"id": u.id, "name": u.name} for u in tasks.mapped("user_ids").sorted("name")]
        branches = []
        if "fm.branch" in self.env:
            branches = [{"id": b.id, "name": b.name}
                        for b in self.env["fm.branch"].sudo().search([("company_id", "in", companies.ids)])]
        sl_options = Task.fields_get(["fm_service_line"])["fm_service_line"]["selection"]
        service_lines = [{"key": k, "name": v} for k, v in sl_options]

        # Per-status counts for the legend (this month)
        status_ids = {}
        for t in in_month:
            status_ids.setdefault(status_of(t), []).append(t.id)

        prev_m = (first - timedelta(days=1)).replace(day=1)
        next_m = (first + timedelta(days=31)).replace(day=1)
        months = [{"num": i, "name": date(2000, i, 1).strftime("%B")} for i in range(1, 13)]
        years = list(range(first.year - 2, first.year + 3))
        return {
            "month_label": first.strftime("%B %Y"),
            "month_start": first.isoformat(),
            "year": first.year,
            "month_num": first.month,
            "months": months,
            "years": years,
            "prev_month": prev_m.isoformat(),
            "next_month": next_m.isoformat(),
            "this_month": today.replace(day=1).isoformat(),
            "weekdays": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            "weeks": weeks,
            "legend": [{"key": k, "label": l, "color": c, "count": len(status_ids.get(k, [])),
                        "ids": status_ids.get(k, [])} for k, l, c in STATUSES],
            "kpis": kpis,
            "kpi_ids": kpi_ids,
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

    @api.model
    def export_board_xlsx(self, month_start=None, technician_id=None, service_line=None, branch_id=None):
        """Every visit of the month the calendar shows, under the same
        filters, as an Excel file — the printout folds busy days into
        "+N more", this does not. Returns {filename, content (base64)}."""
        data = self.get_board_data(month_start, technician_id, service_line, branch_id)
        events = {e["id"]: dict(e, day=fields.Date.to_date(c["date"]))
                  for week in data["weeks"] for c in week if c["in_month"] for e in c["events"]}
        tasks = self.env["project.task"].sudo().browse(list(events)).sorted(lambda t: (t.date_deadline, t.id))
        tz = pytz.timezone(self.env.user.tz or "Asia/Dubai")

        def label(record, field):
            value = record[field] if field in record._fields else False
            return dict(record._fields[field]._description_selection(self.env)).get(value, "") if value else ""

        def local(dt):
            return pytz.utc.localize(dt).astimezone(tz).replace(tzinfo=None) if dt else None

        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {"in_memory": True})
        title = book.add_format({"bold": True, "font_size": 14})
        head = book.add_format({"bold": True, "font_color": "#ffffff", "bg_color": "#1c2b3a", "border": 1, "valign": "vcenter"})
        cell = book.add_format({"border": 1, "valign": "top"})
        day_fmt = book.add_format({"border": 1, "valign": "top", "num_format": "dd-mmm-yyyy"})
        time_fmt = book.add_format({"border": 1, "valign": "top", "num_format": "hh:mm AM/PM"})
        status_fmt = {k: book.add_format({"border": 1, "bold": True, "font_color": "#ffffff", "bg_color": c, "align": "center"})
                      for k, _l, c in STATUSES}

        # Filters as the user set them, so the file says what it contains.
        names = lambda key, rows, field="name": next((r[field] for r in rows if r.get("id", r.get("key")) == key), "")
        filters = [
            ("Month", data["month_label"]),
            ("Company", data["company_label"]),
            ("Technician", names(technician_id, data["technicians"]) if technician_id else "All technicians"),
            ("Service", names(service_line, data["service_lines"]) if service_line else "All services"),
            ("Branch", names(branch_id, data["branches"]) if branch_id else "All branches"),
        ]

        sheet = book.add_worksheet("Visits")
        sheet.write(0, 0, "Maintenance Calendar — %s" % data["month_label"], title)
        sheet.write(1, 0, " · ".join("%s: %s" % f for f in filters[1:]))
        # Minimum widths; text columns grow to their longest value below.
        # Every header also needs room for its filter arrow.
        cols = [("Date", 14), ("Day", 7), ("Time", 11), ("Status", 13), ("Customer", 14), ("Visit", 14),
                ("Technician", 14), ("Service", 12), ("Branch", 12), ("Work Type", 13), ("Severity", 12),
                ("Time Slot", 13), ("Stage", 12), ("Asset", 10), ("Contract", 12)]
        widths = [max(width, len(name) + 5) for name, width in cols]
        for i, (name, _width) in enumerate(cols):
            sheet.write(3, i, name, head)
        row = 4
        for t in tasks:
            ev = events[t.id]
            when = local(t.date_deadline)
            order = (t.fm_contract_order_id if "fm_contract_order_id" in t._fields else False) or t.sale_order_id
            values = [
                # The day the calendar files it under, so the sheet and the
                # grid agree.
                (ev["day"], day_fmt), (ev["day"].strftime("%a"), cell),
                (when if when else "", time_fmt), (ev["status_label"], status_fmt.get(ev["status"], cell)),
                (t.partner_id.display_name or "", cell), (t.name or "", cell),
                (", ".join(t.user_ids.mapped("name")) or "Unassigned", cell), (label(t, "fm_service_line"), cell),
                (t.branch_id.display_name if "branch_id" in t._fields and t.branch_id else "", cell),
                (label(t, "fm_wo_type"), cell), (label(t, "fm_severity"), cell), (label(t, "fm_time_slot"), cell),
                (t.stage_id.name or "", cell), (t.fm_asset_id.display_name if t.fm_asset_id else "", cell),
                (order.name if order else "", cell),
            ]
            for col, (value, fmt) in enumerate(values):
                if hasattr(value, "year"):
                    sheet.write_datetime(row, col, value, fmt)
                else:
                    sheet.write(row, col, value, fmt)
                    widths[col] = max(widths[col], len(str(value)) + 3)
            row += 1
        for col, width in enumerate(widths):
            sheet.set_column(col, col, min(width, 110))
        sheet.freeze_panes(4, 0)
        if row > 4:
            sheet.autofilter(3, 0, row - 1, len(cols) - 1)

        summary = book.add_worksheet("Summary")
        summary.set_column(0, 0, 22)
        summary.set_column(1, 1, 30)
        summary.write(0, 0, "Maintenance Calendar — %s" % data["month_label"], title)
        r = 2
        for name, value in filters:
            summary.write(r, 0, name, head)
            summary.write(r, 1, value, cell)
            r += 1
        r += 1
        kpis = data["kpis"]
        for name, value in [("Today", kpis["today"]), ("Overdue", kpis["overdue"]), ("Unassigned", kpis["unassigned"]),
                            ("This month", kpis["month_total"]), ("Done", kpis["done"]),
                            ("Completion %", kpis["completion"])]:
            summary.write(r, 0, name, head)
            summary.write(r, 1, value, cell)
            r += 1
        r += 1
        for lg in data["legend"]:
            summary.write(r, 0, lg["label"], status_fmt[lg["key"]])
            summary.write(r, 1, lg["count"], cell)
            r += 1
        book.close()
        return {
            "filename": "Maintenance Calendar %s.xlsx" % data["month_label"],
            "content": base64.b64encode(buf.getvalue()).decode(),
        }
