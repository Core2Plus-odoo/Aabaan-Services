# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# The lead-to-job pipeline from the client's process document, in order.
# Each step is reached by its own confirmation; the labels are theirs.
PIPELINE_STAGES = [
    ("lead", "Lead Created"),
    ("qualified", "Sales Qualified"),
    ("accounts", "Accounts Confirmed"),
    ("operations", "Operations Confirmed"),
    ("contracted", "AMC Contract Set Up"),
]


class CrmLead(models.Model):
    """The CRM → Sales → Accounts → Operations handover.

    Their process document runs a lead through five numbered steps before an
    AMC contract exists, and step 4 carries a hard rule: *"Operations
    confirms the customer. Gate: allowed only after Accounts confirmation."*

    Modelled as two dated confirmations rather than CRM stages. Stages are a
    single ordered list, and this handover is not one: step 2 drips the
    qualified lead to Accounts **and** Operations at the same time, and only
    then does the ordering between those two matter. Native CRM stages stay
    free for the sales pipeline, which is what they are for.
    """

    _inherit = "crm.lead"

    fm_sales_qualified_date = fields.Datetime(
        string="Sales Qualified On", readonly=True, copy=False, tracking=True)
    fm_sales_qualified_uid = fields.Many2one(
        "res.users", string="Sales Qualified By", readonly=True, copy=False)

    fm_accounts_confirmed_date = fields.Datetime(
        string="Accounts Confirmed On", readonly=True, copy=False, tracking=True)
    fm_accounts_confirmed_uid = fields.Many2one(
        "res.users", string="Accounts Confirmed By", readonly=True, copy=False)

    fm_ops_confirmed_date = fields.Datetime(
        string="Operations Confirmed On", readonly=True, copy=False, tracking=True)
    fm_ops_confirmed_uid = fields.Many2one(
        "res.users", string="Operations Confirmed By", readonly=True, copy=False)

    fm_pipeline_stage = fields.Selection(
        PIPELINE_STAGES,
        string="FM Pipeline Stage",
        compute="_compute_fm_pipeline_stage",
        store=True,
        index=True,
        help="How far this lead has travelled through the CRM → Sales → "
             "Accounts → Operations handover.",
    )

    # ------------------------------------------------------------------
    # Pipeline position
    # ------------------------------------------------------------------
    @api.depends("fm_sales_qualified_date", "fm_accounts_confirmed_date",
                 "fm_ops_confirmed_date")
    def _compute_fm_pipeline_stage(self):
        """Furthest step the lead has reached.

        Stored so the dashboard funnel ("Leads created / Sales qualified /
        Accounts confirmed / Operations confirmed / AMC contract set up") is
        a group-by rather than five separate counts.
        """
        for lead in self:
            if lead._fm_has_contract():
                lead.fm_pipeline_stage = "contracted"
            elif lead.fm_ops_confirmed_date:
                lead.fm_pipeline_stage = "operations"
            elif lead.fm_accounts_confirmed_date:
                lead.fm_pipeline_stage = "accounts"
            elif lead.fm_sales_qualified_date:
                lead.fm_pipeline_stage = "qualified"
            else:
                lead.fm_pipeline_stage = "lead"

    def _fm_has_contract(self):
        """Whether a sale order exists for this lead.

        ``order_ids`` comes from sale_crm, which bridges CRM and Sales. It is
        resolved at runtime rather than depended on, so this module still
        installs on a database that has CRM without that bridge — the lead
        simply stops at Operations Confirmed instead of showing a contract.
        """
        self.ensure_one()
        if "order_ids" not in self._fields:
            return False
        return bool(self.order_ids)

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------
    @api.constrains("fm_accounts_confirmed_date", "fm_ops_confirmed_date")
    def _check_fm_confirmation_order(self):
        """Operations cannot confirm before Accounts has.

        A constraint, not a check inside the button, so the rule survives
        every other route into the field — import, RPC, a server action, or
        someone clearing the Accounts confirmation after the fact. The
        button gives the friendly message; this is what makes it true.
        """
        for lead in self:
            if lead.fm_ops_confirmed_date and not lead.fm_accounts_confirmed_date:
                raise ValidationError(_(
                    "%(lead)s cannot be confirmed by Operations: Accounts has "
                    "not confirmed it yet.\n\n"
                    "The handover runs Sales → Accounts → Operations, and "
                    "Accounts confirms the commercial side before Operations "
                    "takes the customer on.",
                    lead=lead.display_name,
                ))

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_fm_sales_qualify(self):
        for lead in self:
            if lead.fm_sales_qualified_date:
                continue
            lead.write({
                "fm_sales_qualified_date": fields.Datetime.now(),
                "fm_sales_qualified_uid": self.env.user.id,
            })
            # Step 2 of their flow: the qualified lead goes to Accounts and
            # Operations at the same time. Whoever follows the lead sees it;
            # routing it to named teams needs the client's team membership,
            # which is not settled yet (see the module README).
            lead.message_post(body=_(
                "Sales qualified — handed over to Accounts and Operations."))
        return True

    def action_fm_accounts_confirm(self):
        for lead in self:
            if lead.fm_accounts_confirmed_date:
                continue
            lead.write({
                "fm_accounts_confirmed_date": fields.Datetime.now(),
                "fm_accounts_confirmed_uid": self.env.user.id,
            })
            lead.message_post(body=_(
                "Accounts confirmed — Operations may now confirm."))
        return True

    def action_fm_ops_confirm(self):
        for lead in self:
            if lead.fm_ops_confirmed_date:
                continue
            if not lead.fm_accounts_confirmed_date:
                raise ValidationError(_(
                    "Accounts has not confirmed %(lead)s yet.\n\n"
                    "Operations confirmation is the step after Accounts "
                    "confirmation, not alongside it.",
                    lead=lead.display_name,
                ))
            lead.write({
                "fm_ops_confirmed_date": fields.Datetime.now(),
                "fm_ops_confirmed_uid": self.env.user.id,
            })
            lead.message_post(body=_(
                "Operations confirmed — ready for AMC contract setup."))
        return True
