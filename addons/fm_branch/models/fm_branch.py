# -*- coding: utf-8 -*-
from odoo import api, fields, models

EMIRATES = [
    ("abu_dhabi", "Abu Dhabi"),
    ("dubai", "Dubai"),
    ("sharjah", "Sharjah"),
    ("ajman", "Ajman"),
    ("umm_al_quwain", "Umm Al Quwain"),
    ("ras_al_khaimah", "Ras Al Khaimah"),
    ("fujairah", "Fujairah"),
]


class FmBranch(models.Model):
    _name = "fm.branch"
    _description = "FM Operating Branch"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char()
    emirate = fields.Selection(EMIRATES)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    manager_id = fields.Many2one("res.users", string="Branch Manager")
    phone = fields.Char()
    email = fields.Char()
    street = fields.Char()
    city = fields.Char()
    active = fields.Boolean(default=True)

    contract_count = fields.Integer(compute="_compute_counts")
    workorder_count = fields.Integer(compute="_compute_counts")
    technician_count = fields.Integer(compute="_compute_counts")

    def _compute_counts(self):
        Contract = self.env["fm.contract"]
        Task = self.env["project.task"]
        Emp = self.env["hr.employee"]
        c_groups = dict(Contract._read_group([("branch_id", "in", self.ids)], ["branch_id"], ["__count"]))
        w_groups = dict(Task._read_group([("branch_id", "in", self.ids)], ["branch_id"], ["__count"]))
        e_groups = dict(Emp._read_group([("fm_branch_id", "in", self.ids)], ["fm_branch_id"], ["__count"]))
        for b in self:
            b.contract_count = c_groups.get(b, 0)
            b.workorder_count = w_groups.get(b, 0)
            b.technician_count = e_groups.get(b, 0)

    def action_view_workorders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Work Orders",
            "res_model": "project.task",
            "view_mode": "list,kanban,form",
            "domain": [("branch_id", "=", self.id), ("fm_wo_type", "!=", False)],
            "context": {"default_branch_id": self.id},
        }
