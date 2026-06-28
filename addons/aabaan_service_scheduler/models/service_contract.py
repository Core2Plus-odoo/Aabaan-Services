from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


SERVICE_TYPES = [
    ("pest_control", "Pest Control"),
    ("water_tank", "Water Tank Cleaning"),
    ("cleaning", "Cleaning"),
    ("termite", "Termite"),
    ("other", "Other"),
]


class AabaanServiceContract(models.Model):
    _name = "aabaan.service.contract"
    _description = "Aabaan Service Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_date desc, name desc"

    name = fields.Char(
        string="Contract Reference",
        required=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("aabaan.service.contract") or _("New"),
        tracking=True,
    )
    partner_id = fields.Many2one("res.partner", string="Customer", required=True, tracking=True)
    phone = fields.Char(related="partner_id.phone", readonly=True)
    mobile = fields.Char(related="partner_id.mobile", readonly=True)
    service_type = fields.Selection(SERVICE_TYPES, required=True, default="pest_control", tracking=True)
    product_id = fields.Many2one("product.product", string="Default Service")
    group_name = fields.Char(string="Service Group")
    area = fields.Char(string="Area / Building")
    emirate = fields.Char(string="Emirate")
    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(required=True, tracking=True)
    frequency = fields.Selection(
        [
            ("1", "1 Visit"),
            ("2", "2 Visits"),
            ("4", "4 Visits"),
            ("6", "6 Visits"),
            ("12", "12 Visits"),
            ("24", "24 Visits"),
            ("36", "36 Visits"),
            ("custom", "Custom"),
        ],
        required=True,
        default="12",
        tracking=True,
    )
    custom_visit_count = fields.Integer(string="Custom Visits")
    contract_value = fields.Monetary(required=True, currency_field="currency_id", tracking=True)
    billing_cycle_amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, required=True)
    auto_renew = fields.Boolean()
    salesperson_id = fields.Many2one("res.users", string="Responsible")
    default_technician_ids = fields.Many2many("hr.employee", string="Preferred Technicians")
    notes = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("expired", "Expired"), ("cancelled", "Cancelled")],
        default="draft",
        tracking=True,
    )
    visit_ids = fields.One2many("aabaan.service.visit", "contract_id", string="Visits")
    visit_count = fields.Integer(compute="_compute_visit_stats")
    completed_visit_count = fields.Integer(compute="_compute_visit_stats")
    next_visit_date = fields.Date(compute="_compute_visit_stats", store=True)
    renewal_days = fields.Integer(string="Renewal Alert Days", default=30)
    renewal_due = fields.Boolean(compute="_compute_renewal_due", store=True)

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for contract in self:
            if contract.start_date and contract.end_date and contract.end_date < contract.start_date:
                raise ValidationError(_("End date cannot be before start date."))

    @api.depends("visit_ids.state", "visit_ids.planned_date")
    def _compute_visit_stats(self):
        today = fields.Date.context_today(self)
        for contract in self:
            visits = contract.visit_ids
            contract.visit_count = len(visits)
            contract.completed_visit_count = len(visits.filtered(lambda visit: visit.state == "done"))
            upcoming = visits.filtered(
                lambda visit: visit.state not in ("done", "cancelled") and visit.planned_date >= today
            )
            contract.next_visit_date = min(upcoming.mapped("planned_date")) if upcoming else False

    @api.depends("end_date", "renewal_days", "state")
    def _compute_renewal_due(self):
        today = fields.Date.context_today(self)
        for contract in self:
            contract.renewal_due = (
                contract.state == "active"
                and contract.end_date
                and contract.end_date <= today + timedelta(days=contract.renewal_days or 0)
            )

    def action_activate(self):
        self.write({"state": "active"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_generate_visits(self):
        for contract in self:
            if not contract.start_date or not contract.end_date:
                raise UserError(_("Set start and end dates before generating visits."))
            visit_count = contract._get_visit_count()
            if visit_count <= 0:
                raise UserError(_("Set a valid service frequency before generating visits."))
            existing = contract.visit_ids.filtered(lambda visit: visit.state != "cancelled")
            if existing:
                raise UserError(_("Cancel existing visits before regenerating the schedule."))

            total_days = max((contract.end_date - contract.start_date).days, 1)
            step_days = max(total_days // visit_count, 1)
            vals_list = []
            for index in range(visit_count):
                planned_date = contract.start_date + timedelta(days=step_days * index)
                if planned_date > contract.end_date:
                    planned_date = contract.end_date
                vals_list.append(contract._prepare_visit_vals(index + 1, planned_date))
            self.env["aabaan.service.visit"].create(vals_list)
            contract.state = "active"

    def _get_visit_count(self):
        self.ensure_one()
        if self.frequency == "custom":
            return self.custom_visit_count
        return int(self.frequency or 0)

    def _prepare_visit_vals(self, sequence_number, planned_date):
        self.ensure_one()
        technician_ids = [(6, 0, self.default_technician_ids.ids)] if self.default_technician_ids else False
        return {
            "name": _("%s / Visit %s") % (self.name, sequence_number),
            "contract_id": self.id,
            "partner_id": self.partner_id.id,
            "service_type": self.service_type,
            "product_id": self.product_id.id,
            "planned_date": planned_date,
            "technician_ids": technician_ids,
            "area": self.area,
            "emirate": self.emirate,
            "notes": self.notes,
        }

    @api.model
    def _cron_update_contract_states(self):
        today = fields.Date.context_today(self)
        self.search([("state", "=", "active"), ("end_date", "<", today)]).write({"state": "expired"})
