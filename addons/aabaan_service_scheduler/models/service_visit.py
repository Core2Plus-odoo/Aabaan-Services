from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .service_constants import SERVICE_TYPES


class AabaanServiceVisit(models.Model):
    _name = "aabaan.service.visit"
    _description = "Aabaan Service Visit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_date, priority desc, name"

    name = fields.Char(required=True, tracking=True)
    contract_id = fields.Many2one("aabaan.service.contract", required=True, ondelete="cascade", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Customer", required=True, tracking=True)
    service_type = fields.Selection(SERVICE_TYPES, required=True, default="pest_control", tracking=True)
    product_id = fields.Many2one("product.product", string="Service")
    planned_date = fields.Date(required=True, tracking=True)
    planned_start = fields.Datetime(string="Scheduled Start")
    planned_end = fields.Datetime(string="Scheduled End")
    duration_hours = fields.Float(default=1.0)
    technician_ids = fields.Many2many("hr.employee", string="Technicians", tracking=True)
    area = fields.Char()
    emirate = fields.Char()
    priority = fields.Selection([("0", "Normal"), ("1", "High"), ("2", "Urgent")], default="0")
    state = fields.Selection(
        [
            ("draft", "To Schedule"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("missed", "Missed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )
    completion_date = fields.Date()
    customer_signature = fields.Binary()
    before_notes = fields.Text()
    after_notes = fields.Text()
    materials_used = fields.Text()
    next_recommendation = fields.Text()
    calendar_event_id = fields.Many2one("calendar.event", readonly=True, copy=False)
    color = fields.Integer(compute="_compute_color")

    @api.onchange("planned_date", "planned_start", "duration_hours")
    def _onchange_schedule_time(self):
        for visit in self:
            if visit.planned_start and visit.duration_hours:
                visit.planned_end = visit.planned_start + timedelta(hours=visit.duration_hours)
            elif visit.planned_date and visit.duration_hours and not visit.planned_start:
                visit.planned_start = datetime.combine(visit.planned_date, time(hour=9))
                visit.planned_end = visit.planned_start + timedelta(hours=visit.duration_hours)

    @api.constrains("planned_start", "planned_end")
    def _check_schedule_window(self):
        for visit in self:
            if visit.planned_start and visit.planned_end and visit.planned_end <= visit.planned_start:
                raise ValidationError(_("Scheduled End must be after Scheduled Start."))

    @api.constrains("planned_start", "planned_end", "technician_ids", "state")
    def _check_technician_conflicts(self):
        for visit in self:
            if (
                not visit.planned_start
                or not visit.planned_end
                or not visit.technician_ids
                or visit.state in ("done", "cancelled", "missed")
            ):
                continue
            conflicts = self.search(
                [
                    ("id", "!=", visit.id),
                    ("state", "not in", ("done", "cancelled", "missed")),
                    ("technician_ids", "in", visit.technician_ids.ids),
                    ("planned_start", "<", visit.planned_end),
                    ("planned_end", ">", visit.planned_start),
                ],
                limit=1,
            )
            if conflicts:
                raise ValidationError(_("Technician conflict with %(visit)s.") % {"visit": conflicts.display_name})

    @api.depends("state")
    def _compute_color(self):
        colors = {"draft": 3, "scheduled": 4, "in_progress": 2, "done": 10, "missed": 1, "cancelled": 0}
        for visit in self:
            visit.color = colors.get(visit.state, 0)

    def action_schedule(self):
        for visit in self:
            visit._ensure_default_schedule_window()
            visit.state = "scheduled"
            visit._sync_calendar_event()

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_done(self):
        self.write({"state": "done", "completion_date": fields.Date.context_today(self)})

    def action_missed(self):
        self.write({"state": "missed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reschedule_next_week(self):
        for visit in self:
            visit.planned_date = visit.planned_date + timedelta(days=7)
            if visit.planned_start:
                visit.planned_start = visit.planned_start + timedelta(days=7)
            if visit.planned_end:
                visit.planned_end = visit.planned_end + timedelta(days=7)
            visit.state = "scheduled"
            visit._sync_calendar_event()

    def _ensure_default_schedule_window(self):
        for visit in self:
            if not visit.planned_start:
                visit.planned_start = datetime.combine(visit.planned_date, time(hour=9))
            if not visit.planned_end:
                visit.planned_end = visit.planned_start + timedelta(hours=visit.duration_hours or 1.0)

    def _sync_calendar_event(self):
        Calendar = self.env["calendar.event"]
        for visit in self:
            if not visit.planned_start or not visit.planned_end:
                continue
            partner_ids = visit.contract_id.salesperson_id.partner_id.ids
            values = {
                "name": visit.name,
                "start": visit.planned_start,
                "stop": visit.planned_end,
                "description": visit._calendar_description(),
                "partner_ids": [(6, 0, partner_ids)],
            }
            if visit.calendar_event_id:
                visit.calendar_event_id.write(values)
            else:
                visit.calendar_event_id = Calendar.create(values)

    def _calendar_description(self):
        self.ensure_one()
        technician_names = ", ".join(self.technician_ids.mapped("name"))
        return _("Customer: %(customer)s\nService: %(service)s\nArea: %(area)s\nTechnicians: %(techs)s") % {
            "customer": self.partner_id.display_name,
            "service": dict(SERVICE_TYPES).get(self.service_type, ""),
            "area": self.area or "",
            "techs": technician_names,
        }

    @api.model
    def _cron_mark_missed_visits(self):
        today = fields.Date.context_today(self)
        visits = self.search([("state", "in", ("draft", "scheduled", "in_progress")), ("planned_date", "<", today)])
        visits.write({"state": "missed"})
