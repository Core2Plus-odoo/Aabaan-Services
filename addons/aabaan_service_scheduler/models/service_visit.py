from odoo import fields, models

from .service_constants import SERVICE_TYPES


class AabaanServiceVisit(models.Model):
    _name = "aabaan.service.visit"
    _description = "Aabaan Service Visit"
    _order = "planned_date, name"

    name = fields.Char(required=True)
    contract_id = fields.Many2one("aabaan.service.contract", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", string="Customer", required=True)
    service_type = fields.Selection(SERVICE_TYPES, required=True, default="pest_control")
    product_id = fields.Many2one("product.product", string="Service")
    planned_date = fields.Date(required=True)
    planned_start = fields.Datetime(string="Scheduled Start")
    planned_end = fields.Datetime(string="Scheduled End")
    duration_hours = fields.Float(default=1.0)
    technician_ids = fields.Many2many("hr.employee", string="Technicians")
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
    )
    completion_date = fields.Date()
    before_notes = fields.Text()
    after_notes = fields.Text()
    materials_used = fields.Text()
    next_recommendation = fields.Text()

    def action_schedule(self):
        self.write({"state": "scheduled"})

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_done(self):
        self.write({"state": "done", "completion_date": fields.Date.context_today(self)})

    def action_missed(self):
        self.write({"state": "missed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})
