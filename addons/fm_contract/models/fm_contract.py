# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmContract(models.Model):
    """AMC / break-fix / project contract (brief §5.5).

    Composes with ``sale.order`` via delegation (``_inherits``) so billing,
    currency and the customer come from the standard sales document, while FM
    adds scope, SLA, penalties and a renewal lifecycle.

    ``workorder_ids`` and the data-driven ``health_score`` computation live in
    ``fm_workorder`` / ``fm_sla`` (which depend on this module) to avoid a
    forward dependency on the work-order model. Until then ``health_score`` is a
    plain, manually-maintainable field defaulting to healthy.
    """

    _name = "fm.contract"
    _inherits = {"sale.order": "sale_order_id"}
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "FM Contract"
    _order = "contract_number desc"

    sale_order_id = fields.Many2one(
        "sale.order", required=True, ondelete="restrict", index=True
    )

    # Identity
    contract_number = fields.Char(default="/", readonly=True, copy=False, index=True, tracking=True)
    contract_type = fields.Selection(
        [
            ("amc_comprehensive", "AMC — Comprehensive"),
            ("amc_non_comprehensive", "AMC — Non-Comprehensive"),
            ("break_fix", "Break-Fix Only"),
            ("project", "Project Contract"),
        ],
        required=True,
        default="amc_comprehensive",
        tracking=True,
    )

    # Lifecycle
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("negotiating", "In Negotiation"),
            ("active", "Active"),
            ("renewal_pipeline", "In Renewal Discussion"),
            ("expired", "Expired"),
            ("terminated", "Terminated"),
        ],
        default="draft",
        tracking=True,
    )
    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(required=True, tracking=True)
    auto_renew = fields.Boolean(default=False)
    renewal_term_months = fields.Integer(default=12)
    days_to_renewal = fields.Integer(compute="_compute_days_to_renewal")

    # Financials
    acv = fields.Monetary(string="Annual Contract Value", currency_field="currency_id", tracking=True)
    tcv = fields.Monetary(string="Total Contract Value", compute="_compute_tcv", store=True)
    billing_frequency = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("semi_annual", "Semi-Annual"),
            ("annual", "Annual"),
        ],
        default="monthly",
    )
    next_invoice_date = fields.Date()

    # Scope
    asset_ids = fields.Many2many("fm.asset", string="Covered Assets")
    asset_count = fields.Integer(compute="_compute_asset_count")
    service_inclusions = fields.Many2many(
        "fm.contract.service.item", relation="fm_contract_inclusion_rel",
        column1="contract_id", column2="item_id", string="Service Inclusions",
    )
    service_exclusions = fields.Many2many(
        "fm.contract.service.item", relation="fm_contract_exclusion_rel",
        column1="contract_id", column2="item_id", string="Service Exclusions",
    )

    # SLA & penalties
    sla_rule_ids = fields.One2many("fm.sla.rule", "contract_id", string="SLA Rules")
    penalty_clause_ids = fields.One2many("fm.contract.penalty", "contract_id", string="Penalty Clauses")

    # Health (real computation added in fm_sla; neutral default until then)
    health_score = fields.Float(default=10.0, tracking=True, help="0-10; maintained by fm_sla once work-order history exists.")
    health_band = fields.Selection(
        [
            ("healthy", "Healthy"),
            ("watch", "Watch"),
            ("at_risk", "At Risk"),
            ("critical", "Critical"),
        ],
        default="healthy",
        tracking=True,
    )

    # Account team
    account_manager_id = fields.Many2one("res.users", string="Account Manager", required=True, tracking=True)
    customer_contact_ids = fields.Many2many("res.partner", string="Customer Contacts")

    _contract_number_uniq = models.Constraint(
        "unique(contract_number)", "Contract number must be unique."
    )

    @api.depends("acv", "start_date", "end_date")
    def _compute_tcv(self):
        for c in self:
            if c.acv and c.start_date and c.end_date and c.end_date > c.start_date:
                years = (c.end_date - c.start_date).days / 365.0
                c.tcv = c.acv * years
            else:
                c.tcv = c.acv

    def _compute_days_to_renewal(self):
        today = fields.Date.context_today(self)
        for c in self:
            c.days_to_renewal = (c.end_date - today).days if c.end_date else 0

    def _compute_asset_count(self):
        for c in self:
            c.asset_count = len(c.asset_ids)

    @api.depends("contract_number", "sale_order_id.name")
    def _compute_display_name(self):
        for c in self:
            c.display_name = c.contract_number if c.contract_number and c.contract_number != "/" else (c.sale_order_id.name or "New Contract")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("contract_number", "/") in (False, "/"):
                vals["contract_number"] = self.env["ir.sequence"].next_by_code("fm.contract") or "/"
        return super().create(vals_list)

    def action_activate(self):
        self.write({"state": "active"})

    def action_set_renewal(self):
        self.write({"state": "renewal_pipeline"})

    def action_terminate(self):
        self.write({"state": "terminated"})
