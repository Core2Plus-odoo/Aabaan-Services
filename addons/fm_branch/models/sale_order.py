# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.fm_fsm.models.fm_visit_schedule_mixin import FREQUENCY_PER_YEAR

# Dubai Local Order No. 11, which the client's own Studio rule cites by
# name, sets a minimum number of pest control visits a year and turns
# that minimum on whether the premises handle food.
#
# Scoped to Dubai on purpose. The regulation is Dubai Municipality's,
# and applying it to a Sharjah or Fujairah contract would be inventing
# a rule for an emirate that has not been checked. If the other
# emirates impose their own floors, they go here as their own entries
# once somebody has read them -- not by assuming Dubai's travel.
VISIT_FLOOR_PER_YEAR = {
    ("dubai", "food"): 24,
    ("dubai", "non_food"): 12,
}
VISIT_FLOOR_AUTHORITY = "Dubai Local Order No. 11"


class SaleOrder(models.Model):
    """Branch on the sale order itself.

    ``fm.contract`` composes with ``sale.order`` by delegation
    (``_inherits``), so holding the branch here means one field and one
    column serving both apps: a contract shows it in the FM cockpit, and
    the same value is on the quotation or order in Sales, where contracts
    are also written up.

    Keeping a separate ``branch_id`` on ``fm.contract`` would shadow this
    one and give the same contract two branches, so the field lives here
    only.
    """

    _inherit = "sale.order"

    branch_id = fields.Many2one(
        "fm.branch", string="Branch", index=True, tracking=True,
        help="The Aabaan branch delivering this contract. Groups contracts, "
             "work orders and reporting by emirate.")

    @api.onchange("branch_id")
    def _onchange_branch_id_agreement_template(self):
        """Re-suggest a wording template when the branch changes and the
        current template (if any) doesn't match this branch. Same rule as
        the legacy contract model; the lookup is shared (fm.agreement.mixin),
        only the covered-assets field name differs."""
        if not self._fm_branch_template_needs_resuggesting():
            return
        service_line = self._fm_infer_service_from_assets(self.fm_asset_ids)
        template = self._fm_branch_template_for_service(service_line)
        if template:
            self.agreement_template_id = template.id

    # ------------------------------------------------------------------
    # What the branch contributes to a contract
    # ------------------------------------------------------------------
    fm_licence_number = fields.Char(
        string="Operating Licence No.",
        related="branch_id.licence_number",
        readonly=True,
        help="The licence the delivering branch operates under. Printed on "
             "the service agreement; set it on the branch, not here.",
    )

    @api.onchange("branch_id")
    def _onchange_branch_id_callout_allowance(self):
        """Offer the branch's standard allowance to a contract that has
        none of its own.

        Only ever fills a blank. A contract that already promises a number
        promised it to somebody, and changing the branch on an existing
        contract must not quietly rewrite what the customer agreed to.
        """
        for order in self:
            if order.fm_callout_allowance:
                continue
            order.fm_callout_allowance = order.branch_id.default_callout_allowance

    def _fm_fill_from_branch(self):
        """Same fill, for the orders no form ever touched.

        The onchange above covers somebody typing into the contract. An
        order built by import, RPC or a server action never runs it, and
        those are exactly the contracts nobody is watching -- so the fill
        happens again on confirmation, and says on the chatter that it
        happened. A term the customer can hold us to should not appear
        with nothing on the record to say where it came from.
        """
        for order in self:
            allowance = order.branch_id.default_callout_allowance
            if not allowance or order.fm_callout_allowance:
                continue
            order.fm_callout_allowance = allowance
            order.message_post(body=_(
                "No call-out allowance was set, so the %(branch)s standard of "
                "%(count)s was applied. Correct it on the contract if the "
                "agreement says otherwise.",
                branch=order.branch_id.display_name, count=allowance,
            ))

    def action_confirm(self):
        """Fill after ``super()``, not before.

        fm_branch loads last, so this is the first ``action_confirm`` in
        the chain -- and at that point an order that Sales wrote as an
        ordinary quotation is not yet marked as a contract.
        ``_fm_autodetect_contracts`` recognises it further down, inside
        ``super()``. Filling first would hand the branch's allowance to
        contracts somebody remembered to tick and silently skip exactly
        the ones nobody did, which are the contracts least likely to have
        an allowance of their own.

        Nothing downstream reads the allowance during confirmation, so
        unlike fm_subscription's plan there is no reason to be early.
        """
        res = super().action_confirm()
        self.filtered("is_fm_contract")._fm_fill_from_branch()
        return res

    # ------------------------------------------------------------------
    # The municipal visit floor
    # ------------------------------------------------------------------
    def _fm_visits_per_year(self):
        """How many visits a year this contract's cadence delivers."""
        self.ensure_one()
        if self.visit_frequency == "custom":
            days = self.custom_interval_days
            return (365.0 / days) if days > 0 else 0
        return FREQUENCY_PER_YEAR.get(self.visit_frequency, 0)

    def _fm_visit_floor(self):
        """The minimum visits a year this contract is obliged to, and who
        obliges it. ``(0, None)`` when no rule here covers it."""
        self.ensure_one()
        emirate = self.branch_id.emirate
        if not emirate or not self.fm_premises_type:
            # Not enough is known to impose a floor, and a floor guessed
            # from half the facts is worse than none: it would block
            # contracts nobody has established a rule for.
            return 0, None
        floor = VISIT_FLOOR_PER_YEAR.get((emirate, self.fm_premises_type))
        return (floor, VISIT_FLOOR_AUTHORITY) if floor else (0, None)

    @api.constrains(
        "state", "is_fm_contract", "branch_id", "fm_premises_type",
        "visit_frequency", "custom_interval_days",
    )
    def _check_fm_visit_floor(self):
        """Refuse to confirm a contract that sells fewer visits than the
        emirate requires.

        A constraint rather than a check inside the confirm button,
        because the same rule has to hold for import, RPC and a server
        action -- and because the hole a button leaves is not confirming
        an under-frequency contract but *editing* a confirmed one down to
        one, which a button never sees.

        Only confirmed contracts are checked. A quotation is a
        negotiation, and a draft that cannot be saved at twelve visits
        while somebody is still working out whether the site handles food
        would make the form unusable.
        """
        for order in self:
            if order.state not in ("sale", "done") or not order.is_fm_contract:
                continue
            floor, authority = order._fm_visit_floor()
            if not floor:
                continue
            sold = order._fm_visits_per_year()
            if sold >= floor:
                continue
            raise ValidationError(_(
                "%(authority)s requires at least %(floor)s visits a year for "
                "%(premises)s premises in %(emirate)s. This contract is set "
                "to %(sold)s.\n\n"
                "Raise the visit frequency on the Scheduling tab, or correct "
                "the premises type if the site does not handle food.",
                authority=authority,
                floor=floor,
                premises=dict(order._fields["fm_premises_type"].selection).get(
                    order.fm_premises_type, order.fm_premises_type),
                emirate=dict(order.branch_id._fields["emirate"].selection).get(
                    order.branch_id.emirate, order.branch_id.emirate),
                sold=int(sold) if float(sold).is_integer() else round(sold, 1),
            ))
