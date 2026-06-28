from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

from .service_constants import SERVICE_TYPES


class AabaanServiceContract(models.Model):
    _name = "aabaan.service.contract"
    _description = "Aabaan Service Contract"
    _order = "start_date desc, name desc"

    name = fields.Char(string="Contract Reference", required=True, copy=False, default="New")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
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
    visit_count = fields.Integer(compute="_compute_visit_count")

    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("aabaan.service.contract") or "New"
        return super().create(vals_list)

    def _compute_visit_count(self):
        counts = {
            contract.id: count
            for contract, count in self.env["aabaan.service.visit"]._read_group(
                [("contract_id", "in", self.ids)], ["contract_id"], ["__count"]
            )
        }
        for contract in self:
            contract.visit_count = counts.get(contract.id, 0)

    def _planned_visit_count(self):
        self.ensure_one()
        if self.frequency == "custom":
            return self.custom_visit_count
        return int(self.frequency)

    def action_generate_visits(self):
        self.ensure_one()
        if self.visit_ids:
            raise UserError(_("Visits already exist for this contract. Remove them first to regenerate."))
        if self.start_date >= self.end_date:
            raise UserError(_("The end date must be after the start date."))
        count = self._planned_visit_count()
        if count <= 0:
            raise UserError(_("Set a visit count greater than zero before generating visits."))

        total_days = (self.end_date - self.start_date).days
        interval_days = total_days / count
        visit_vals = [self._prepare_visit_values(index, interval_days) for index in range(count)]
        return self.env["aabaan.service.visit"].create(visit_vals)

    def action_view_visits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visits"),
            "res_model": "aabaan.service.visit",
            "view_mode": "list,calendar,kanban,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id, "default_partner_id": self.partner_id.id},
        }

    def _prepare_visit_values(self, index, interval_days):
        self.ensure_one()
        visit_date = self.start_date + timedelta(days=round(interval_days * index))
        return {
            "name": _("%(ref)s - Visit %(num)s") % {"ref": self.name, "num": index + 1},
            "company_id": self.company_id.id,
            "contract_id": self.id,
            "partner_id": self.partner_id.id,
            "service_type": self.service_type,
            "product_id": self.product_id.id,
            "planned_date": visit_date,
            "area": self.area,
            "emirate": self.emirate,
            "technician_ids": [(6, 0, self.default_technician_ids.ids)],
            "state": "draft",
        }
