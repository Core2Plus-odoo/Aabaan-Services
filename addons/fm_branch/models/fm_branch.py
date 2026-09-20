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

    # Moved here from fm_exec_dashboard when that dashboard was retired: a
    # branch's revenue target and currency belong to the branch, not to
    # whichever screen happens to read them.
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True)
    monthly_revenue_target = fields.Monetary(
        string="Monthly Revenue Target",
        currency_field="currency_id",
        help="Target revenue for this branch in a calendar month, excluding "
             "tax. Zero means no target is set \u2014 a dashboard then shows no "
             "target rather than inferring one from history, because a target "
             "is a management decision.",
    )

    # ------------------------------------------------------------------
    # What this emirate requires of us
    # ------------------------------------------------------------------
    # A branch is the company operating in one emirate, and each emirate
    # licenses and regulates that operation separately. These two answer
    # "what does trading here oblige us to?", so they belong on the branch
    # rather than on every contract written from it -- and as configuration
    # rather than as constants in code, because a licence is renewed and a
    # standard allowance is a commercial decision, neither of which should
    # need a deployment.
    #
    # Both are deliberately blank. The Studio layer these came from carries
    # figures, but a licence number printed on a customer's signed agreement
    # and an allowance the customer can hold us to are not things to inherit
    # from an undocumented server action on the say-so of whoever wrote it.
    # Blank prints nothing, which is visibly wrong; a wrong number prints
    # confidently, which is not.
    licence_number = fields.Char(
        string="Operating Licence No.",
        help="The trade or operating licence this branch works under in its "
             "emirate, as it should appear on the printed service "
             "agreement. Blank prints nothing rather than a guess.",
    )
    default_callout_allowance = fields.Integer(
        string="Standard Free Call-Outs",
        help="How many complaint call-outs a contract written from this "
             "branch normally includes in its price. Filled onto a new "
             "contract that does not set its own, and the contract can "
             "always override it. Zero means this branch includes none as "
             "standard.",
    )

    contract_count = fields.Integer(compute="_compute_counts")
    workorder_count = fields.Integer(compute="_compute_counts")
    technician_count = fields.Integer(compute="_compute_counts")

    def _compute_counts(self):
        """A contract is a sale order flagged is_fm_contract, and that is
        now the only kind there is — the de-duplication this used to do
        against the legacy fm.contract model went with that model, so a
        plain grouped count is enough again."""
        Order = self.env["sale.order"]
        Task = self.env["project.task"]
        Emp = self.env["hr.employee"]
        c_groups = dict(Order._read_group(
            [("branch_id", "in", self.ids), ("is_fm_contract", "=", True)],
            ["branch_id"], ["__count"],
        ))
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
