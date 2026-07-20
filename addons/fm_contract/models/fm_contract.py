# -*- coding: utf-8 -*-
from odoo import api, fields, models


class FmContract(models.Model):
    """AMC / break-fix / project contract (brief §5.5).

    Composes with ``sale.order`` via delegation (``_inherits``) so billing,
    currency and the customer come from the standard sales document, while FM
    adds scope, SLA, penalties and a renewal lifecycle.

    Visits/work orders are linked by ``fm_fsm`` (``task_ids`` on this model →
    native FSM ``project.task``). ``health_score`` / ``health_band`` are
    account-manager-maintained fields (10 = healthy); no automatic computation.
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

    # Health (maintained by the account manager; 10 = healthy)
    health_score = fields.Float(default=10.0, tracking=True, help="0-10; set by the account manager from delivery/SLA performance.")
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

    # Printed legal agreement (fm_documents "Service Agreement" report) — free
    # text so each contract can carry its own site-specific wording, with
    # sensible defaults so a blank contract still prints something reasonable.
    subject = fields.Char(
        string="Contract Subject",
        help="Printed under the contract header, e.g. 'PEST CONTROL TREATMENT "
        "FOR ROYAL APARTMENT G+11'. Defaults to the customer name if blank.",
    )
    scope_notes = fields.Text(
        string="Scope of Work (site wording)",
        help="Free text describing the areas/site covered, printed on the "
        "agreement. Falls back to the Inclusions list if blank.",
    )
    treatment_notes = fields.Text(
        string="Treatment / Method Notes",
        help="Optional — treatment methods, chemicals/equipment used, etc. "
        "Only printed if set.",
    )
    payment_terms_note = fields.Text(
        string="Payment Terms (printed wording)",
        help="e.g. '50% at the time of signing, 50% after 6 months'.",
    )
    unscheduled_visits_included = fields.Integer(
        string="Unscheduled Visits Included",
        default=2,
        help="Number of unscheduled/ad-hoc visits included at no extra charge "
        "over the contract term, stated on the printed agreement.",
    )
    termination_notice_days = fields.Integer(
        string="Termination Notice (days)",
        default=30,
        help="Notice period either party must give to cancel auto-renewal, "
        "stated on the printed agreement.",
    )
    complaint_response_hours = fields.Integer(
        string="Complaint Response Time (hours)",
        default=24,
        help="Hours within which the team commits to visiting a site after a "
        "complaint/infestation report, stated on the printed quotation.",
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
