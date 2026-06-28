from odoo import fields, models

from .service_constants import SERVICE_TYPES


class AabaanServiceContract(models.Model):
    _name = "aabaan.service.contract"
    _description = "Aabaan Service Contract"
    _order = "start_date desc, name desc"

    name = fields.Char(string="Contract Reference", required=True, copy=False, default="New")
    partner_id = fields.Many2one("res.partner", string="Customer", required=True)
    phone = fields.Char(related="partner_id.phone", readonly=True)
    service_type = fields.Selection(SERVICE_TYPES, required=True, default="pest_control")
    product_id = fields.Many2one("product.product", string="Default Service")
    area = fields.Char(string="Area / Building")
    emirate = fields.Char(string="Emirate")
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
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
    )
    custom_visit_count = fields.Integer(string="Custom Visits")
    contract_value = fields.Monetary(currency_field="currency_id")
    billing_cycle_amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, required=True)
    auto_renew = fields.Boolean()
    salesperson_id = fields.Many2one("res.users", string="Responsible")
    default_technician_ids = fields.Many2many("hr.employee", string="Preferred Technicians")
    notes = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("expired", "Expired"), ("cancelled", "Cancelled")],
        default="draft",
    )
    visit_ids = fields.One2many("aabaan.service.visit", "contract_id", string="Visits")
