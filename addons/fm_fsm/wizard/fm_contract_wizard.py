# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

STEPS = [
    ("customer", "Customer"),
    ("service", "Services & Agreements"),
    ("products", "Products & Pricing"),
    ("schedule", "Visit Schedule"),
    ("review", "Review & Create"),
]
STEP_ORDER = [s[0] for s in STEPS]

# fm.asset.category.default_ppm_frequency_months -> contract visit_frequency
MONTHS_TO_FREQUENCY = {1: "monthly", 2: "bi_monthly", 3: "quarterly", 6: "semi_annual", 12: "annual"}

FREQUENCY_SELECTION = [
    ("weekly", "Weekly"),
    ("fortnightly", "Every 2 Weeks"),
    ("monthly", "Monthly"),
    ("bi_monthly", "Every 2 Months"),
    ("quarterly", "Quarterly"),
    ("semi_annual", "Semi-Annual"),
    ("annual", "Annual"),
    ("custom", "Custom — enter interval"),
]
FREQUENCY_PER_YEAR = {
    "weekly": 52, "fortnightly": 26, "monthly": 12, "bi_monthly": 6,
    "quarterly": 4, "semi_annual": 2, "annual": 1,
}


class FmContractWizard(models.TransientModel):
    """Guided, step-by-step contract creation.

    One dialog, five steps — Customer, Services & Agreements, Products &
    Pricing, Visit Schedule, Review. A customer can take SEVERAL services
    for the same site (e.g. Pest Control + Water Tank Cleaning); each
    selected service gets its own agreement template, its own visit
    frequency, and its own contract — mirroring how Aaban's real documents
    work (one signed agreement per service) — all created in a single run
    and opened together on the visit calendar.
    """

    _name = "fm.contract.wizard"
    _description = "New Contract (Guided)"

    step = fields.Selection(STEPS, default="customer", required=True)

    # ---- Step 1: Customer ----
    partner_id = fields.Many2one(
        "res.partner", string="Customer",
        help="Pick an existing customer, or type a new name and choose "
        "'Create' to add one on the spot.",
    )
    site_name = fields.Char(
        string="Site / Building",
        help="The site this contract covers, e.g. 'ROYAL APARTMENT G+11'. "
        "Registered as a covered asset so visits can be scheduled against it.",
    )

    # ---- Step 2: Services & Agreements ----
    service_ids = fields.Many2many(
        "fm.asset.category", string="Services",
        help="Tick every service this customer is taking for the site. One "
        "agreement (contract) is created per service — matching how each "
        "service is legally a separate signed document.",
    )
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
    template_preview = fields.Text(
        compute="_compute_template_preview", string="Matched Agreements"
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
    schedule_ids = fields.One2many(
        "fm.contract.wizard.schedule", "wizard_id", string="Per-service Schedule"
    )
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
        compute="_compute_planned_visit_count", string="Projected Visits (all services)"
    )
    contract_count_preview = fields.Integer(compute="_compute_contract_count_preview")

    # ------------------------------------------------------------------
    # Computes & onchanges
    # ------------------------------------------------------------------
    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id and not self.site_name:
            self.site_name = self.partner_id.name

    @api.onchange("service_ids")
    def _onchange_service_ids(self):
        """Keep the per-service schedule rows and pricing-line service tags
        in sync with the ticked services.

        The rows are fully rebuilt on every change — carrying the user's
        frequency edits over BY VALUE for still-selected services. (An
        earlier version tried to keep existing rows via (6,0,_origin.ids)
        commands, but _origin is empty for rows that only exist in the
        unsaved dialog, which could yield schedule rows with no category_id
        and a "Missing required value for the field 'Service'" error on
        Next.)"""
        current = {
            s.category_id.id: (s.visit_frequency, s.custom_interval_days)
            for s in self.schedule_ids if s.category_id
        }
        rows = []
        for cat in self.service_ids:
            freq, days = current.get(
                cat.id,
                (MONTHS_TO_FREQUENCY.get(cat.default_ppm_frequency_months, "monthly"), 0),
            )
            rows.append((0, 0, {
                "category_id": cat.id,
                "visit_frequency": freq or "monthly",
                "custom_interval_days": days,
            }))
        self.schedule_ids = [(5, 0, 0)] + rows
        # Single service selected -> tag any untagged pricing lines with it.
        if len(self.service_ids) == 1:
            for line in self.line_ids.filtered(lambda l: not l.service_id):
                line.service_id = self.service_ids.id

    def _find_wizard_template(self, service_line):
        """Hook: fm_branch extends this to prefer a branch+service match."""
        return self.env["fm.contract.agreement.template"].search(
            [("service_line", "=", service_line)], limit=1
        )

    @api.depends("service_ids")
    def _compute_template_preview(self):
        for w in self:
            if not w.service_ids:
                w.template_preview = _("Tick at least one service above.")
                continue
            parts = []
            for cat in w.service_ids:
                template = w._find_wizard_template(cat.service_line)
                if template:
                    extras = ", ".join(template.line_ids.mapped("name"))
                    parts.append(
                        _("• %(service)s → \"%(template)s\"%(extra)s") % {
                            "service": cat.name,
                            "template": template.name,
                            "extra": _(" (includes: %s)") % extras if extras else "",
                        }
                    )
                else:
                    parts.append(
                        _("• %(service)s → standard generic wording (no template yet)")
                        % {"service": cat.name}
                    )
            parts.append(_(
                "\nOne agreement per service is created; every paragraph stays "
                "editable on each contract's Printed Agreement tab."
            ))
            w.template_preview = "\n".join(parts)

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

    @api.depends("schedule_ids.visit_frequency", "schedule_ids.custom_interval_days",
                 "start_date", "end_date")
    def _compute_planned_visit_count(self):
        for w in self:
            years = 1.0
            if w.start_date and w.end_date and w.end_date > w.start_date:
                years = ((w.end_date - w.start_date).days + 1) / 365.0
            total = 0
            for row in w.schedule_ids:
                if row.visit_frequency == "custom":
                    interval = max(1, row.custom_interval_days or 30)
                else:
                    interval = max(1, round(365 / FREQUENCY_PER_YEAR.get(row.visit_frequency, 12)))
                total += max(1, round((365.0 / interval) * years))
            w.planned_visit_count = total

    @api.depends("service_ids")
    def _compute_contract_count_preview(self):
        for w in self:
            w.contract_count_preview = len(w.service_ids)

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
            if not self.service_ids:
                raise UserError(_("Tick at least one service."))
        elif self.step == "products":
            if len(self.service_ids) > 1:
                untagged = self.line_ids.filtered(lambda l: not l.service_id)
                if untagged:
                    raise UserError(_(
                        "With several services selected, set the Service column "
                        "on every pricing line so each amount lands on the right "
                        "contract."
                    ))
        elif self.step == "schedule":
            if not self.start_date or not self.end_date or self.end_date <= self.start_date:
                raise UserError(_("Set a valid start date and term."))
            if self.auto_schedule:
                bad = self.schedule_ids.filtered(
                    lambda s: s.visit_frequency == "custom" and not s.custom_interval_days
                )
                if bad:
                    raise UserError(_(
                        "Enter the custom interval (days) for: %s"
                    ) % ", ".join(bad.mapped("category_id.name")))

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
    def _get_or_create_site_asset(self, category):
        """Register the covered site as an fm.asset in this service's
        category (visit generation requires a covered asset; one asset per
        site+service so each contract schedules independently)."""
        self.ensure_one()
        Asset = self.env["fm.asset"]
        existing = Asset.search(
            [("name", "=", self.site_name), ("category_fm_id", "=", category.id)], limit=1
        )
        if existing:
            return existing
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

    def _prepare_contract_vals(self, category, template):
        """Hook: fm_branch extends this to add branch_id."""
        self.ensure_one()
        return {
            "partner_id": self.partner_id.id,
            "service_line": category.service_line,
            "contract_type": self.contract_type,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "renewal_term_months": self.term_months or 12,
            "account_manager_id": self.env.user.id,
            "agreement_template_id": template.id if template else False,
            "subject": "%s FOR %s" % (category.name.upper(), (self.site_name or "").upper()),
        }

    def _create_contracts(self):
        """One contract per selected service, sharing customer/site/term."""
        self.ensure_one()
        self._validate_step()
        contracts = self.env["fm.contract"]
        single_service = len(self.service_ids) == 1
        for category in self.service_ids:
            template = self._find_wizard_template(category.service_line)
            contract = self.env["fm.contract"].create(
                self._prepare_contract_vals(category, template)
            )
            # Onchanges don't fire on create() — apply the template wording
            # (or the generic defaults) explicitly, exactly as the form would.
            contract._apply_agreement_template_wording()
            row = self.schedule_ids.filtered(lambda s: s.category_id == category)[:1]
            contract.write({
                "auto_schedule": self.auto_schedule,
                "visit_frequency": row.visit_frequency or "monthly",
                "custom_interval_days": row.custom_interval_days,
                "visit_start_time": self.visit_start_time,
                "visit_duration_hours": self.visit_duration_hours,
                "skip_weekends": self.skip_weekends,
                "preferred_technician_id": self.preferred_technician_id.id or False,
                "auto_schedule_state": self.auto_schedule_state,
                "asset_ids": [(4, self._get_or_create_site_asset(category).id)],
            })
            lines = self.line_ids if single_service else self.line_ids.filtered(
                lambda l: l.service_id == category
            )
            for line in lines:
                self.env["sale.order.line"].create({
                    "order_id": contract.sale_order_id.id,
                    "product_id": line.product_id.id,
                    "name": line.name or line.product_id.display_name,
                    "product_uom_qty": line.quantity,
                    "price_unit": line.price_unit,
                })
            if contract.amount_untaxed:
                contract.acv = contract.amount_untaxed
            contracts |= contract
        return contracts

    def _action_open_contracts(self, contracts):
        if len(contracts) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Contract"),
                "res_model": "fm.contract",
                "res_id": contracts.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("New Contracts"),
            "res_model": "fm.contract",
            "view_mode": "list,form",
            "domain": [("id", "in", contracts.ids)],
            "target": "current",
        }

    def action_create_draft(self):
        contracts = self._create_contracts()
        return self._action_open_contracts(contracts)

    def action_create_and_schedule(self):
        contracts = self._create_contracts()
        contracts.action_activate()  # generates visits when auto_schedule is on
        tasks = contracts.mapped("task_ids")
        if not self.auto_schedule or not tasks:
            return self._action_open_contracts(contracts)
        return {
            "type": "ir.actions.act_window",
            "name": _("%s — Visit Calendar") % (self.site_name or self.partner_id.name),
            "res_model": "project.task",
            "view_mode": "calendar,list,form",
            "view_id": False,
            "domain": [("fm_contract_id", "in", contracts.ids)],
            "context": {},
            "target": "current",
        }


class FmContractWizardLine(models.TransientModel):
    _name = "fm.contract.wizard.line"
    _description = "New Contract (Guided) — Product Line"

    wizard_id = fields.Many2one("fm.contract.wizard", required=True, ondelete="cascade")
    service_id = fields.Many2one(
        "fm.asset.category", string="Service",
        domain="[('id', 'in', allowed_service_ids)]",
        help="Which service's contract this amount belongs to (required when "
        "several services are selected).",
    )
    allowed_service_ids = fields.Many2many(related="wizard_id.service_ids")
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
            if not self.service_id and len(self.wizard_id.service_ids) == 1:
                self.service_id = self.wizard_id.service_ids.id

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit


class FmContractWizardSchedule(models.TransientModel):
    _name = "fm.contract.wizard.schedule"
    _description = "New Contract (Guided) — Per-service Visit Schedule"

    wizard_id = fields.Many2one("fm.contract.wizard", required=True, ondelete="cascade")
    category_id = fields.Many2one("fm.asset.category", string="Service", required=True)
    visit_frequency = fields.Selection(
        FREQUENCY_SELECTION, string="Frequency", default="monthly", required=True
    )
    custom_interval_days = fields.Integer(string="Every N Days")
