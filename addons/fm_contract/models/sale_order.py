# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES


class SaleOrder(models.Model):
    """A contract is a sale order.

    This is where FM contracts are written now. The order already carries the
    customer, the priced service lines, the currency, the taxes, the
    signature, the invoicing and the delivery status; what FM adds is the
    part a sale order has no opinion about — which assets are covered, what
    the SLA promises, how the contract renews, and the wording that gets
    printed and signed.

    Two rules shape this layer:

    **Nothing is required at database level.** Every field here is optional,
    because most sale orders in this database are ordinary quotations that
    know nothing about facility management, and a required column would stop
    them saving. What makes a field mandatory is being a contract, so the
    form makes them ``required="is_fm_contract"`` instead. Requiredness that
    depends on a flag belongs in the view; requiredness that is always true
    belongs in the column, and none of these are always true.

    **The order's own state is not re-implemented.** Draft, sent, confirmed
    and cancelled are what ``sale.order.state`` already means, and the
    original ``fm.contract`` duplicated the first two as "draft" and "in
    negotiation" — a second status field saying nearly the same thing, free
    to disagree with the first. ``fm_lifecycle`` starts where the order's
    state stops: the contract goes Active when the order is confirmed, and
    from there moves to renewal, expiry or termination.
    """

    _name = "sale.order"
    _inherit = ["sale.order", "fm.agreement.mixin"]

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    is_fm_contract = fields.Boolean(
        string="Facility Management Contract",
        copy=False,
        tracking=True,
        help="Tick this to manage the order as an FM contract: covered "
             "assets, SLA rules, a renewal lifecycle and the printed service "
             "agreement. Unticked orders behave as ordinary quotations.",
    )
    fm_contract_number = fields.Char(
        string="Contract Number",
        copy=False,
        readonly=True,
        index=True,
        help="Assigned from the AMC sequence the first time the order is "
             "marked as an FM contract. The order keeps its own SO number "
             "as well — one is the sales document, the other is what the "
             "customer's signed agreement is filed under.",
    )
    fm_contract_type = fields.Selection(
        [
            ("amc_comprehensive", "AMC — Comprehensive"),
            ("amc_non_comprehensive", "AMC — Non-Comprehensive"),
            ("break_fix", "Break-Fix Only"),
            ("project", "Project Contract"),
        ],
        string="Contract Type",
        default="amc_comprehensive",
        tracking=True,
    )
    fm_service_line = fields.Selection(
        SERVICE_LINES,
        string="Service",
        tracking=True,
        help="What service this contract covers — drives which Agreement "
             "Wording Template is auto-selected (and, with fm_branch "
             "installed, combined with the contract's Branch/Emirate).",
    )

    # ------------------------------------------------------------------
    # Lifecycle — picks up where sale.order.state leaves off
    # ------------------------------------------------------------------
    fm_lifecycle = fields.Selection(
        [
            ("active", "Active"),
            ("renewal_pipeline", "In Renewal Discussion"),
            ("expired", "Expired"),
            ("terminated", "Terminated"),
        ],
        string="Contract Stage",
        copy=False,
        tracking=True,
        help="Where the contract is after the order was confirmed. Blank "
             "until confirmation — until then the order's own status "
             "(draft / sent) is the whole story.",
    )
    fm_start_date = fields.Date(string="Start Date", tracking=True)
    fm_end_date = fields.Date(string="End Date", tracking=True)
    fm_auto_renew = fields.Boolean(string="Auto-Renew", default=False)
    fm_renewal_term_months = fields.Integer(string="Renewal Term (months)", default=12)
    fm_days_to_renewal = fields.Integer(
        string="Days to Renewal", compute="_compute_fm_days_to_renewal"
    )

    # ------------------------------------------------------------------
    # Commercials
    # ------------------------------------------------------------------
    fm_acv = fields.Monetary(
        string="Annual Contract Value", currency_field="currency_id",
        aggregator="sum", tracking=True,
    )
    fm_tcv = fields.Monetary(
        string="Total Contract Value", currency_field="currency_id",
        aggregator="sum", compute="_compute_fm_tcv", store=True,
    )
    fm_billing_frequency = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("semi_annual", "Semi-Annual"),
            ("annual", "Annual"),
        ],
        string="Billing Frequency",
        default="monthly",
    )
    fm_next_invoice_date = fields.Date(string="Next Invoice Date")

    # ------------------------------------------------------------------
    # Scope
    # ------------------------------------------------------------------
    fm_asset_ids = fields.Many2many(
        "fm.asset", relation="fm_contract_order_asset_rel",
        column1="order_id", column2="asset_id", string="Covered Assets",
    )
    fm_asset_count = fields.Integer(compute="_compute_fm_asset_count")
    fm_service_inclusions = fields.Many2many(
        "fm.contract.service.item", relation="fm_contract_order_inclusion_rel",
        column1="order_id", column2="item_id", string="Service Inclusions",
    )
    fm_service_exclusions = fields.Many2many(
        "fm.contract.service.item", relation="fm_contract_order_exclusion_rel",
        column1="order_id", column2="item_id", string="Service Exclusions",
    )

    # ------------------------------------------------------------------
    # SLA, penalties, printed agreement
    # ------------------------------------------------------------------
    fm_sla_rule_ids = fields.One2many("fm.sla.rule", "order_id", string="SLA Rules")
    fm_penalty_clause_ids = fields.One2many(
        "fm.contract.penalty", "order_id", string="Penalty Clauses"
    )
    agreement_line_ids = fields.One2many(
        "fm.contract.agreement.line", "order_id",
        string="Additional Terms (editable)",
        help="Extra articles for this service (e.g. Tank Details, Warranty "
             "Certificate, Customer Responsibility) — copied from the selected "
             "template's Additional Terms, then freely editable/addable here "
             "without touching the shared template.",
    )

    # ------------------------------------------------------------------
    # Health & account team
    # ------------------------------------------------------------------
    fm_health_score = fields.Float(
        string="Health Score", default=10.0, tracking=True,
        help="0-10; set by the account manager from delivery/SLA performance.",
    )
    fm_health_band = fields.Selection(
        [
            ("healthy", "Healthy"),
            ("watch", "Watch"),
            ("at_risk", "At Risk"),
            ("critical", "Critical"),
        ],
        string="Health",
        default="healthy",
        tracking=True,
    )
    fm_account_manager_id = fields.Many2one(
        "res.users", string="Account Manager", tracking=True
    )
    fm_customer_contact_ids = fields.Many2many(
        "res.partner", relation="fm_contract_order_contact_rel",
        column1="order_id", column2="partner_id", string="Customer Contacts",
    )

    _fm_contract_number_uniq = models.Constraint(
        "unique(fm_contract_number)", "Contract number must be unique."
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("fm_acv", "fm_start_date", "fm_end_date")
    def _compute_fm_tcv(self):
        for order in self:
            if (
                order.fm_acv
                and order.fm_start_date
                and order.fm_end_date
                and order.fm_end_date > order.fm_start_date
            ):
                years = (order.fm_end_date - order.fm_start_date).days / 365.0
                order.fm_tcv = order.fm_acv * years
            else:
                order.fm_tcv = order.fm_acv

    def _compute_fm_days_to_renewal(self):
        today = fields.Date.context_today(self)
        for order in self:
            order.fm_days_to_renewal = (
                (order.fm_end_date - today).days if order.fm_end_date else 0
            )

    def _compute_fm_asset_count(self):
        for order in self:
            order.fm_asset_count = len(order.fm_asset_ids)

    # ------------------------------------------------------------------
    # Agreement wording — the rules live in fm.agreement.mixin
    # ------------------------------------------------------------------
    @api.onchange("fm_service_line")
    def _onchange_fm_service_line_agreement_template(self):
        """Primary trigger: as soon as a Service is picked (right after the
        customer, before assets necessarily exist), apply the matching
        Agreement Wording Template."""
        self._fm_apply_template_for_service(self.fm_service_line)

    @api.onchange("fm_asset_ids")
    def _onchange_fm_asset_ids_agreement_template(self):
        """Secondary trigger: infer the service from covered assets when
        Service wasn't set directly, without overriding an explicit choice."""
        if self.fm_service_line or self.agreement_template_id or not self.fm_asset_ids:
            return
        service_line = self._fm_infer_service_from_assets(self.fm_asset_ids)
        if service_line and self._fm_apply_template_for_service(service_line):
            self.fm_service_line = service_line

    @api.onchange("agreement_template_id")
    def _onchange_agreement_template_id(self):
        """Manual template pick/change from the Printed Agreement page."""
        self._apply_agreement_template_wording()

    # ------------------------------------------------------------------
    # Contract numbering
    # ------------------------------------------------------------------
    def _fm_assign_contract_numbers(self):
        """Give every FM contract without one the next AMC number.

        Numbers are handed out when an order becomes a contract, not when it
        is created: an ordinary quotation must not burn a contract number,
        and most orders in this database never become contracts.
        """
        sequence = self.env["ir.sequence"]
        for order in self:
            if order.is_fm_contract and not order.fm_contract_number:
                order.fm_contract_number = sequence.next_by_code("fm.contract")

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._fm_assign_contract_numbers()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if vals.get("is_fm_contract"):
            self._fm_assign_contract_numbers()
        return res

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_confirm(self):
        """Confirming the order is what makes the contract live.

        One action, one meaning: the customer has agreed, so the sales
        document is confirmed and the contract starts. Nobody has to
        remember a second button, and there is no window where the order is
        confirmed but the contract is not.
        """
        res = super().action_confirm()
        contracts = self.filtered(lambda o: o.is_fm_contract and not o.fm_lifecycle)
        if contracts:
            contracts.write({"fm_lifecycle": "active"})
        return res

    def _fm_require_contract(self):
        non_contracts = self.filtered(lambda o: not o.is_fm_contract)
        if non_contracts:
            raise UserError(_(
                "These orders are not FM contracts, so they have no contract "
                "stage to move: %s",
                ", ".join(non_contracts.mapped("name")),
            ))

    def action_fm_set_renewal(self):
        self._fm_require_contract()
        self.write({"fm_lifecycle": "renewal_pipeline"})

    def action_fm_terminate(self):
        self._fm_require_contract()
        self.write({"fm_lifecycle": "terminated"})

    def action_fm_reactivate(self):
        self._fm_require_contract()
        self.write({"fm_lifecycle": "active"})
