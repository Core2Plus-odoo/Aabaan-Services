from odoo import _, fields, models
from odoo.exceptions import UserError


class AabaanAssignTechnicianWizard(models.TransientModel):
    _name = "aabaan.assign.technician.wizard"
    _description = "Assign Technicians to Service Visits"

    visit_ids = fields.Many2many(
        "aabaan.service.visit",
        string="Visits",
        required=True,
        default=lambda self: self.env.context.get("active_ids"),
    )
    technician_ids = fields.Many2many("hr.employee", string="Technicians", required=True)

    def action_assign(self):
        self.ensure_one()
        visits = self.visit_ids.filtered(lambda visit: visit.state not in ("done", "cancelled"))
        if not visits:
            raise UserError(_("Select at least one visit that is not done or cancelled."))
        visits.write({"technician_ids": [(6, 0, self.technician_ids.ids)]})
        visits.filtered(lambda visit: visit.state == "draft").action_schedule()
        return {"type": "ir.actions.act_window_close"}
