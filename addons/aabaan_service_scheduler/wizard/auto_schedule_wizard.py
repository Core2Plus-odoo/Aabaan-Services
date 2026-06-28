from datetime import datetime, time, timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.service_constants import SERVICE_TYPES


class AabaanAutoScheduleWizard(models.TransientModel):
    _name = "aabaan.auto.schedule.wizard"
    _description = "Auto Schedule Service Visits"

    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=lambda self: fields.Date.context_today(self) + timedelta(days=7))
    service_type = fields.Selection(SERVICE_TYPES, string="Service Type")
    emirate = fields.Char()
    area = fields.Char()
    technician_ids = fields.Many2many("hr.employee", string="Available Technicians", required=True)
    default_start_hour = fields.Integer(string="Default Start Hour", default=9)

    def _build_visit_domain(self):
        self.ensure_one()
        domain = [
            ("state", "=", "draft"),
            ("planned_date", ">=", self.date_from),
            ("planned_date", "<=", self.date_to),
        ]
        if self.service_type:
            domain.append(("service_type", "=", self.service_type))
        if self.emirate:
            domain.append(("emirate", "=", self.emirate))
        if self.area:
            domain.append(("area", "=", self.area))
        return domain

    def _is_technician_free(self, technician, start, stop):
        conflict = self.env["aabaan.service.visit"].search(
            [
                ("technician_ids", "in", technician.id),
                ("state", "in", ("scheduled", "in_progress")),
                ("planned_start", "<", stop),
                ("planned_end", ">", start),
            ],
            limit=1,
        )
        return not conflict

    def action_auto_schedule(self):
        self.ensure_one()
        if not self.technician_ids:
            raise UserError(_("Select at least one available technician."))

        visits = self.env["aabaan.service.visit"].search(self._build_visit_domain(), order="priority desc, planned_date")
        technicians = list(self.technician_ids)
        rotation = 0
        scheduled = self.env["aabaan.service.visit"]
        skipped = self.env["aabaan.service.visit"]

        for visit in visits:
            start = visit.planned_start or datetime.combine(visit.planned_date, time(hour=self.default_start_hour))
            stop = start + timedelta(hours=visit.duration_hours or 1.0)
            assigned_technician = False
            for offset in range(len(technicians)):
                candidate = technicians[(rotation + offset) % len(technicians)]
                if self._is_technician_free(candidate, start, stop):
                    assigned_technician = candidate
                    rotation = (rotation + offset + 1) % len(technicians)
                    break
            if not assigned_technician:
                skipped += visit
                continue
            visit.write(
                {
                    "technician_ids": [(6, 0, [assigned_technician.id])],
                    "planned_start": start,
                    "planned_end": stop,
                    "state": "scheduled",
                }
            )
            scheduled += visit

        message = _("Scheduled %(scheduled)s visit(s).") % {"scheduled": len(scheduled)}
        if skipped:
            message += " " + _("%(skipped)s visit(s) skipped due to no available technician.") % {
                "skipped": len(skipped)
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Auto Schedule"), "message": message, "sticky": False},
        }
