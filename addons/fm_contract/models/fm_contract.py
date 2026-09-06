# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES


class FmContract(models.Model):
    """AMC / break-fix / project contract (brief §5.5).

    Composes with ``sale.order`` via delegation (``_inherits``) so billing,
    currency and the customer come from the standard sales document, while FM
    adds scope, SLA, penalties and a renewal lifecycle.

    Visits/work orders are linked by ``fm_fsm`` (``fm_task_ids`` on this model →
    native FSM ``project.task``). ``health_score`` / ``health_band`` are
    account-manager-maintained fields (10 = healthy); no automatic computation.
    """

    _name = "fm.contract"
    _inherits = {"sale.order": "sale_order_id"}
    _inherit = ["mail.thread", "mail.activity.mixin", "fm.agreement.mixin"]
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
    service_line = fields.Selection(
        SERVICE_LINES,
        string="Service",
        tracking=True,
        help="What service this contract covers — drives which Agreement "
        "Wording Template is auto-selected (and, with fm_branch installed, "
        "combined with the contract's Branch/Emirate).",
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

    agreement_line_ids = fields.One2many(
        "fm.contract.agreement.line", "contract_id",
        string="Additional Terms (editable)",
        help="Extra articles for this service (e.g. Tank Details, Warranty "
        "Certificate, Customer Responsibility) — copied from the selected "
        "template's Additional Terms, then freely editable/addable here "
        "without touching the shared template.",
    )

    @api.onchange("service_line")
    def _onchange_service_line_agreement_template(self):
        """Primary trigger: as soon as a Service is picked, apply the matching
        Agreement Wording Template (rules in fm.agreement.mixin)."""
        self._fm_apply_template_for_service(self.service_line)

    @api.onchange("asset_ids")
    def _onchange_asset_ids_agreement_template(self):
        """Secondary trigger: infer the service from covered assets when
        Service wasn't set directly, without overriding an explicit choice."""
        if self.service_line or self.agreement_template_id or not self.asset_ids:
            return
        service_line = self._fm_infer_service_from_assets(self.asset_ids)
        if service_line and self._fm_apply_template_for_service(service_line):
            self.service_line = service_line

    @api.onchange("agreement_template_id")
    def _onchange_agreement_template_id(self):
        """Manual template pick/change from the Printed Agreement page."""
        self._apply_agreement_template_wording()

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
        self._fm_check_creation_allowed()
        for vals in vals_list:
            if vals.get("contract_number", "/") in (False, "/"):
                vals["contract_number"] = self.env["ir.sequence"].next_by_code("fm.contract") or "/"
        return super().create(vals_list)

    @api.model
    def _fm_check_creation_allowed(self):
        """Contracts are written in Sales now, not here.

        A contract is a sale order: fm.contract already wraps one by
        delegation, and the platform is consolidating onto the order itself
        so there is a single place a commitment to a customer is made, a
        single thing to quote, sign, schedule visits from and invoice.

        create="0" on the views only hides the New button. This is the check
        that actually holds, because the button is not the only way in --
        import, RPC and a stray script all reach create() directly.

        The escape hatch is a context key rather than a group: the people who
        legitimately still need this are code paths (data migration, tests),
        not a category of user. Nobody gets a permanent right to reopen a
        door the platform is closing.
        """
        if self.env.context.get("fm_allow_contract_create"):
            return
        raise UserError(_(
            "FM contracts are no longer created here.\n\n"
            "Create the contract as a quotation in Sales and confirm it. The "
            "visit schedule, invoicing and the customer's signed document all "
            "follow from that order, so the order is the one record that has "
            "to be right.\n\n"
            "Existing FM contracts stay readable and editable; only creating "
            "new ones has moved."))

    def action_activate(self):
        self.write({"state": "active"})

    def action_set_renewal(self):
        self.write({"state": "renewal_pipeline"})

    def action_terminate(self):
        self.write({"state": "terminated"})


class FmContractAgreementLine(models.Model):
    """One custom article on a contract's printed agreement — the contract's
    own editable copy of a template line (see
    FmContract._onchange_agreement_template_id); freely addable/editable
    without touching the shared template."""

    _name = "fm.contract.agreement.line"
    _description = "FM Contract Agreement — Additional Term"
    _order = "sequence, id"

    order_id = fields.Many2one(
        "sale.order", string="Contract", ondelete="cascade", index=True
    )
    contract_id = fields.Many2one(
        "fm.contract", string="Contract (legacy)", ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Heading", required=True)
    body = fields.Text(string="Body", required=True)
