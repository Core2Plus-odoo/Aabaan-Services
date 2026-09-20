# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES

# Shared with sale.order.template, which carries the same choices as a
# contract profile. One list, so a profile can never offer a contract type
# or a billing cadence the order does not understand.
CONTRACT_TYPES = [
    ("amc_comprehensive", "AMC — Comprehensive"),
    ("amc_non_comprehensive", "AMC — Non-Comprehensive"),
    ("break_fix", "Break-Fix Only"),
    ("project", "Project Contract"),
]

BILLING_FREQUENCIES = [
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("semi_annual", "Semi-Annual"),
    ("annual", "Annual"),
]


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
        compute="_compute_fm_from_template", store=True, readonly=False,
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
        CONTRACT_TYPES,
        string="Contract Type",
        default="amc_comprehensive",
        tracking=True,
        compute="_compute_fm_from_template", store=True, readonly=False,
    )
    fm_service_line = fields.Selection(
        SERVICE_LINES,
        string="Service",
        tracking=True,
        compute="_compute_fm_from_template", store=True, readonly=False,
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
    # Labelled "Contract Start/End", not "Start/End Date". sale_subscription
    # already puts start_date and end_date on sale.order, and two fields on one
    # model sharing a label is not cosmetic: Odoo warns about it at every
    # registry load, and import/export by column name becomes ambiguous.
    #
    # The deeper fix is to drop these two and use the subscription pair, which
    # is what a contract term already means on a sale order. Not done blind:
    # those fields drive the recurrence and next-invoice date when an order has
    # a subscription plan, and this environment cannot reach an instance to
    # check what writing them on a non-subscription order does. It needs one
    # test against a real database, not a guess. fm_command_centre's
    # FIELD_ALIASES already reads whichever pair exists, so that change costs
    # the dashboard nothing.
    fm_start_date = fields.Date(
        string="Contract Start", tracking=True,
        compute="_compute_fm_from_template", store=True, readonly=False,
    )
    fm_end_date = fields.Date(
        string="Contract End", tracking=True,
        compute="_compute_fm_end_date", store=True, readonly=False,
    )
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
        BILLING_FREQUENCIES,
        string="Billing Frequency",
        default="monthly",
        compute="_compute_fm_from_template", store=True, readonly=False,
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
        "res.users", string="Account Manager", tracking=True,
        compute="_compute_fm_from_template", store=True, readonly=False,
    )
    # Redefined from fm.agreement.mixin so the contract profile can fill it:
    # a compute may only assign the fields it declares, and the branch/asset
    # onchanges that also set it still work because this stays editable.
    agreement_template_id = fields.Many2one(
        "fm.contract.agreement.template",
        string="Agreement Wording Template",
        compute="_compute_fm_from_template", store=True, readonly=False,
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

    # ------------------------------------------------------------------
    # Contract profiles: the quotation template fills the FM fields in
    # ------------------------------------------------------------------
    # Odoo applies a quotation template through stored, editable computes --
    # _compute_note, _compute_validity_date and _compute_require_signature in
    # sale_management all have this shape. Following it rather than an
    # onchange means the profile also lands on an order created by import,
    # RPC or a server action, and `readonly=False` keeps every filled value
    # editable afterwards.
    #
    # Note the asymmetry, which is Odoo's and not ours: the template's order
    # *lines* are copied by _onchange_sale_order_template_id, so they only
    # appear when somebody picks the template in the form. The FM fields
    # here fill either way.
    #
    # One compute for the whole profile rather than one per field: they are
    # filled together from a single source, and eight near-identical methods
    # would only be eight places for them to drift apart.
    @api.depends("sale_order_template_id")
    def _compute_fm_from_template(self):
        for order in self:
            profile = order.sale_order_template_id
            # ``_origin`` rather than reading the field itself. While a
            # compute runs its own fields are *protected*, and a protected
            # read on an unsaved record returns False rather than what is
            # there (fields.py, Field.__get__: ``if env.is_protected(...):
            # value = convert_to_cache(False, ...)``). So ``order.x or
            # default`` inside x's own compute silently discards whatever
            # the user typed. ``_origin`` is the persisted record -- itself
            # for a saved order, empty for a brand new one -- so this reads
            # the real stored value without re-entering the compute.
            saved = order._origin
            if not profile or not profile.fm_is_contract_profile:
                # Not a contract profile: keep what is already stored. A
                # compute must still assign on every record, or the field
                # comes back unset instead of defaulted.
                order.is_fm_contract = saved.is_fm_contract
                order.fm_service_line = saved.fm_service_line
                order.fm_contract_type = saved.fm_contract_type or "amc_comprehensive"
                order.fm_billing_frequency = saved.fm_billing_frequency or "monthly"
                order.fm_start_date = saved.fm_start_date
                order.fm_account_manager_id = saved.fm_account_manager_id
                order.agreement_template_id = saved.agreement_template_id
                continue
            order.is_fm_contract = True
            order.fm_service_line = profile.fm_service_line or saved.fm_service_line
            order.fm_contract_type = profile.fm_contract_type or "amc_comprehensive"
            order.fm_billing_frequency = profile.fm_billing_frequency or "monthly"
            # Start today unless a date is already set. A contract written
            # now almost always starts now, and an end date cannot be
            # derived from a term without one.
            order.fm_start_date = saved.fm_start_date or fields.Date.context_today(order)
            order.fm_account_manager_id = (
                profile.fm_account_manager_id
                or saved.fm_account_manager_id
                or order.env.user
            )
            order.agreement_template_id = (
                profile.fm_agreement_template_id or saved.agreement_template_id
            )

    @api.depends("sale_order_template_id", "fm_start_date")
    def _compute_fm_end_date(self):
        """End date = start + the profile's term.

        Separate from the profile compute because it also has to follow the
        start date being changed by hand, which is the common edit: a
        customer signs for the standard twelve months, starting in March.
        """
        for order in self:
            profile = order.sale_order_template_id
            term = profile.fm_term_months if profile.fm_is_contract_profile else 0
            if term and order.fm_start_date:
                order.fm_end_date = order.fm_start_date + relativedelta(months=term)
            else:
                order.fm_end_date = order.fm_end_date

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
    # ------------------------------------------------------------------
    # Recognising a contract that was written in Sales
    # ------------------------------------------------------------------
    def _fm_contract_signals(self):
        """Why this order reads as an FM contract. Empty means it does not.

        The signals are returned as readable phrases rather than a bare
        boolean because they are posted to the order's chatter: a contract
        that appeared in the FM app on its own has to be able to say what
        made it one.
        """
        self.ensure_one()
        signals = []
        services = self.order_line.product_id.filtered("fm_is_contract_service")
        if services:
            signals.append(_(
                "it sells %s",
                ", ".join(services.mapped("display_name")),
            ))
        # sale_subscription is Enterprise and may not be installed; a
        # recurring plan is the sales document already saying "this repeats".
        if "plan_id" in self._fields and self.plan_id:
            signals.append(_("it runs on the %s plan", self.plan_id.display_name))
        if self.fm_service_line:
            signals.append(_("an FM service line is set on it"))
        if self.fm_start_date or self.fm_end_date:
            signals.append(_("it carries a contract term"))
        if self.fm_asset_ids:
            signals.append(_("it covers %s asset(s)", len(self.fm_asset_ids)))
        return signals

    def _fm_fill_contract_term(self):
        """Give a newly recognised contract the term it needs to schedule.

        A contract ticked by hand gets its dates from the form, which makes
        them required. One recognised on confirmation has no form to fill
        them in, and a contract with no term generates no visits — so the
        dates are derived, and what was derived is said out loud on the
        chatter rather than left to be discovered.
        """
        self.ensure_one()
        assumed = []
        start = self.fm_start_date
        if not start:
            start = fields.Date.to_date(self.date_order) or fields.Date.context_today(self)
            self.fm_start_date = start
            assumed.append(_("start %s (the order date)", start))
        if not self.fm_end_date:
            months = self.fm_renewal_term_months or 12
            end = start + relativedelta(months=months) - relativedelta(days=1)
            self.fm_end_date = end
            assumed.append(_("end %s (%s-month term)", end, months))
        return assumed

    def _fm_autodetect_contracts(self):
        """Tick is_fm_contract on confirmation for orders that are contracts.

        The FM app lists contracts as the sale orders carrying
        ``is_fm_contract``. Leaving that tick to the person writing the
        quotation means an AMC agreed in Sales is invisible to Operations
        until somebody notices — the schedule is never generated and the
        renewal never appears. So confirmation, which is the moment the
        customer has agreed, is also the moment the order is recognised.

        Only orders that show a positive signal are touched: an ordinary
        quotation stays an ordinary quotation, and an order somebody
        deliberately left unticked can be unticked again afterwards.
        """
        for order in self.filtered(lambda o: not o.is_fm_contract):
            signals = order._fm_contract_signals()
            if not signals:
                continue
            order.is_fm_contract = True
            assumed = order._fm_fill_contract_term()
            body = _(
                "Recognised as a Facility Management contract on confirmation "
                "because %s. It now appears under FM → Contracts.",
                "; ".join(signals),
            )
            if assumed:
                body += " " + _(
                    "No contract term was set, so one was derived: %s. Correct "
                    "it on the contract if the agreement says otherwise.",
                    "; ".join(assumed),
                )
            order.message_post(body=body)

    def action_confirm(self):
        """Confirming the order is what makes the contract live.

        One action, one meaning: the customer has agreed, so the sales
        document is confirmed and the contract starts. Nobody has to
        remember a second button, and there is no window where the order is
        confirmed but the contract is not.

        The recognition runs *before* ``super()`` so that everything hanging
        off confirmation further down the chain — the contract number, the
        lifecycle, and fm_fsm's visit generation — sees an order that is
        already marked as a contract.
        """
        self._fm_autodetect_contracts()
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
