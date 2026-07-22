# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.fm_asset.models.fm_asset_category import SERVICE_LINES

STEPS = [
    ("customer", "Customer"),
    ("service", "Service & Agreement"),
    ("products", "Products & Pricing"),
    ("schedule", "Visit Schedule"),
    ("review", "Review & Create"),
]
STEP_ORDER = [s[0] for s in STEPS]


class FmContractWizard(models.TransientModel):
    """Guided, step-by-step contract creation.

    One dialog, five steps — Customer, Service & Agreement, Products &
    Pricing, Visit Schedule, Review — ending in a ready contract with its
    agreement wording applied, products priced, the site registered as a
    covered asset (required for visit generation), and optionally the whole
    visit schedule generated and opened on the calendar.
    """

    _name = "fm.contract.wizard"
    _description = "New Contract (Guided)"

    step = fields.Selection(STEPS, default="customer", required=True)

    # ---- Step 1: Customer ----
    partner_id = fields.Many2one(
        "res.partner", string="Customer",
        domain=[("is_company", "in", [True, False])],
        help="Pick an existing customer, or type a new name and choose "
        "'Create' to add one on the spot.",
    )
    site_name = fields.Char(
        string="Site / Building",
        help="The site this contract covers, e.g. 'ROYAL APARTMENT G+11'. "
        "Registered as the contract's covered asset so visits can be "
        "scheduled against it.",
    )

    # ---- Step 2: Service & Agreement ----
    service_line = fields.Selection(SERVICE_LINES, string="Service")
    contract_type = fields.Selection(
        [
            ("amc_comprehensive", "AMC — Comprehensive"),
            ("amc_non_comprehensive", "AMC — Non-Comprehensive"),
            ("break_fix", "Break-Fix Only"),
            ("project", "Project Contract"),
        ],
        default="amc_comprehensive",
        required=True,
        string="Contract Type",
    )
    template_id = fields.Many2one(
        "fm.contract.agreement.template",
        string="Agreement Template",
        help="Matched automatically from the service (and branch, where "
        "applicable). The wording is copied onto the contract where you can "
        "edit every paragraph freely.",
    )
    template_preview = fields.Text(
        compute="_compute_template_preview", string="Wording Preview"
    )

    # ---- Step 3: Products & Pricing ----
    line_ids = fields.One2many("fm.contract.wizard.line", "wizard_id", string="Lines")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    amount_untaxed = fields.Monetary(
        compute="_compute_amounts", string="Subtotal", currency_field="currency_id"
    )

    # ---- Step 4: Visit Schedule ----
    start_date = fields.Date(default=fields.Date.context_today, required=True)
    term_months = fields.Integer(string="Term (months)", default=12)
    end_date = fields.Date(compute="_compute_end_date", store=True, readonly=False, required=True)
    auto_schedule = fields.Boolean(string="Auto-schedule Visits", default=True)
    visit_frequency = fields.Selection(
        [
            ("weekly", "Weekly"),
            ("fortnightly", "Every 2 Weeks"),
            ("monthly", "Monthly"),
            ("bi_monthly", "Every 2 Months"),
            ("quarterly", "Quarterly"),
            ("semi_annual", "Semi-Annual"),
            ("annual", "Annual"),
            ("custom", "Custom — enter interval"),
        ],
        default="monthly",
        string="Visit Frequency",
    )
    custom_interval_days = fields.Integer(string="Custom Interval (days)")
    visit_start_time = fields.Float(string="Visit Start Time", default=9.0)
    visit_duration_hours = fields.Float(string="Visit Duration (hours)", default=2.0)
    skip_weekends = fields.Boolean(string="Skip Weekends", default=True)
    preferred_technician_id = fields.Many2one("hr.employee", string="Preferred Technician")
    auto_schedule_state = fields.Selection(
        [
            ("draft", "Draft — needs review before dispatch"),
            ("confirmed", "Confirmed — ready to assign/dispatch"),
        ],
        default="confirmed",
        string="Visits Start As",
    )
    planned_visit_count = fields.Integer(
        compute="_compute_planned_visit_count", string="Projected Visits"
    )

    # ------------------------------------------------------------------
    # Computes & onchanges
    # ------------------------------------------------------------------
    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id and not self.site_name:
            self.site_name = self.partner_id.name

    @api.onchange("service_line")
    def _onchange_service_line(self):
        if self.service_line:
            self.template_id = self._find_wizard_template()

    def _find_wizard_template(self):
        """Hook: fm_branch extends this to prefer a branch+service match."""
        return self.env["fm.contract.agreement.template"].search(
            [("service_line", "=", self.service_line)], limit=1
        )

    @api.depends("template_id")
    def _compute_template_preview(self):
        for w in self:
            t = w.template_id
            if not t:
                w.template_preview = _(
                    "No service template matched — the contract will use the "
                    "standard generic wording (fully editable after creation)."
                )
                continue
            parts = []
            if t.quotation_intro_text:
                parts.append(_("QUOTATION INTRO\n%s") % t.quotation_intro_text)
            if t.scope_method_text:
                parts.append(_("SCOPE OF WORK\n%s") % t.scope_method_text)
            if t.service_text:
                parts.append(_("ARTICLE 2 — SERVICE\n%s") % t.service_text)
            if t.schedule_text:
                parts.append(_("ARTICLE 4 — SERVICE SCHEDULE\n%s") % t.schedule_text)
            if t.exclusions_default_text:
                parts.append(_("DEFAULT EXCLUSIONS\n%s") % t.exclusions_default_text)
            for line in t.line_ids:
                parts.append("%s\n%s" % (line.name.upper(), line.body))
            w.template_preview = "\n\n".join(parts) or _(
                "This template has no wording yet — edit it under "
                "Contracts → Agreement Templates."
            )

    @api.depends("line_ids.price_subtotal")
    def _compute_amounts(self):
        for w in self:
            w.amount_untaxed = sum(w.line_ids.mapped("price_subtotal"))

    @api.depends("start_date", "term_months")
    def _compute_end_date(self):
        for w in self:
            if w.start_date and w.term_months:
                w.end_date = w.start_date + relativedelta(months=w.term_months, days=-1)
            elif not w.end_date:
                w.end_date = False

    @api.depends("visit_frequency", "custom_interval_days", "start_date", "end_date")
    def _compute_planned_visit_count(self):
        per_year = {
            "weekly": 52, "fortnightly": 26, "monthly": 12, "bi_monthly": 6,
            "quarterly": 4, "semi_annual": 2, "annual": 1,
        }
        for w in self:
            if w.visit_frequency == "custom":
                interval = max(1, w.custom_interval_days or 30)
            else:
                interval = max(1, round(365 / per_year.get(w.visit_frequency, 12)))
            years = 1.0
            if w.start_date and w.end_date and w.end_date > w.start_date:
                years = ((w.end_date - w.start_date).days + 1) / 365.0
            w.planned_visit_count = max(1, round((365.0 / interval) * years))

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _validate_step(self):
        self.ensure_one()
        if self.step == "customer":
            if not self.partner_id:
                raise UserError(_("Pick (or create) the customer first."))
            if not self.site_name:
                raise UserError(_("Enter the site/building this contract covers."))
        elif self.step == "service":
            if not self.service_line:
                raise UserError(_("Select the service this contract is for."))
        elif self.step == "schedule":
            if not self.start_date or not self.end_date or self.end_date <= self.start_date:
                raise UserError(_("Set a valid start date and term."))
            if self.auto_schedule and self.visit_frequency == "custom" and not self.custom_interval_days:
                raise UserError(_("Enter the custom interval in days."))

    def action_next(self):
        self.ensure_one()
        self._validate_step()
        idx = STEP_ORDER.index(self.step)
        self.step = STEP_ORDER[min(idx + 1, len(STEP_ORDER) - 1)]
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        idx = STEP_ORDER.index(self.step)
        self.step = STEP_ORDER[max(idx - 1, 0)]
        return self._reopen()

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    def _get_or_create_site_asset(self):
        """Register the covered site as an fm.asset (visit generation
        requires at least one covered asset on the contract)."""
        self.ensure_one()
        Asset = self.env["fm.asset"]
        existing = Asset.search([("name", "=", self.site_name)], limit=1)
        if existing:
            return existing
        category = self.env["fm.asset.category"].search(
            [("service_line", "=", self.service_line)], limit=1
        ) or self.env["fm.asset.category"].search([], limit=1)
        if not category:
            category = self.env["fm.asset.category"].create(
                {"name": _("General"), "service_line": self.service_line or "other"}
            )
        location = self.env["fm.asset.location"].search(
            [("name", "=", self.site_name)], limit=1
        ) or self.env["fm.asset.location"].create(
            {"name": self.site_name, "location_type": "site"}
        )
        return Asset.create({
            "name": self.site_name,
            "category_fm_id": category.id,
            "location_fm_id": location.id,
        })

    def _prepare_contract_vals(self):
        """Hook: fm_branch extends this to add branch_id."""
        self.ensure_one()
        service_label = dict(SERVICE_LINES).get(self.service_line, "")
        return {
            "partner_id": self.partner_id.id,
            "service_line": self.service_line,
            "contract_type": self.contract_type,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "renewal_term_months": self.term_months or 12,
            "account_manager_id": self.env.user.id,
            "agreement_template_id": self.template_id.id or False,
            "subject": "%s FOR %s" % (service_label.upper(), (self.site_name or "").upper()),
        }

    def _create_contract(self):
        self.ensure_one()
        self._validate_step()
        contract = self.env["fm.contract"].create(self._prepare_contract_vals())
        # Onchanges don't fire on create() — apply the template wording (or
        # the generic defaults) explicitly, exactly as the form would.
        contract._apply_agreement_template_wording()
        contract.write({
            "auto_schedule": self.auto_schedule,
            "visit_frequency": self.visit_frequency,
            "custom_interval_days": self.custom_interval_days,
            "visit_start_time": self.visit_start_time,
            "visit_duration_hours": self.visit_duration_hours,
            "skip_weekends": self.skip_weekends,
            "preferred_technician_id": self.preferred_technician_id.id or False,
            "auto_schedule_state": self.auto_schedule_state,
            "asset_ids": [(4, self._get_or_create_site_asset().id)],
        })
        for line in self.line_ids:
            self.env["sale.order.line"].create({
                "order_id": contract.sale_order_id.id,
                "product_id": line.product_id.id,
                "name": line.name or line.product_id.display_name,
                "product_uom_qty": line.quantity,
                "price_unit": line.price_unit,
            })
        if contract.amount_untaxed:
            contract.acv = contract.amount_untaxed
        return contract

    def action_create_draft(self):
        contract = self._create_contract()
        return {
            "type": "ir.actions.act_window",
            "name": _("Contract"),
            "res_model": "fm.contract",
            "res_id": contract.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_and_schedule(self):
        contract = self._create_contract()
        contract.action_activate()  # generates visits when auto_schedule is on
        if not self.auto_schedule or not contract.task_ids:
            return {
                "type": "ir.actions.act_window",
                "name": _("Contract"),
                "res_model": "fm.contract",
                "res_id": contract.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("%s — Visit Calendar") % contract.display_name,
            "res_model": "project.task",
            "view_mode": "calendar,list,form",
            "view_id": False,
            "domain": [("fm_contract_id", "=", contract.id)],
            "context": {"default_fm_contract_id": contract.id},
            "target": "current",
        }


class FmContractWizardLine(models.TransientModel):
    _name = "fm.contract.wizard.line"
    _description = "New Contract (Guided) — Product Line"

    wizard_id = fields.Many2one("fm.contract.wizard", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product / Service", required=True)
    name = fields.Char(string="Description")
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Float(string="Unit Price")
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    price_subtotal = fields.Monetary(
        compute="_compute_subtotal", string="Subtotal", currency_field="currency_id"
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.price_unit = self.product_id.lst_price

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
