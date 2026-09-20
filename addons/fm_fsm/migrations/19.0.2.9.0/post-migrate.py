# -*- coding: utf-8 -*-
"""Carry the legacy fm.contract records onto the sale orders they wrap.

A contract is a sale order. ``fm.contract`` wraps one by delegation and is
frozen — ``create()`` refuses, and the wizard that used to write to it is
deactivated — but the records written before the move are still real
contracts with real visits, and their orders carry none of the FM fields.
Until this runs they are reachable only through the admin-only "Contracts
(legacy)" menu: not in FM → Contracts, not in the Command Centre, not in
any renewal figure.

So each legacy contract's values are copied onto its own order and the
order is marked ``is_fm_contract``. Nothing is deleted here — the
fm.contract rows, the visits' ``fm_contract_id`` links and the legacy menu
all stay, so this is verifiable on production before the model itself is
retired.

**Why this lives in fm_fsm rather than fm_contract**, whose model it is:
the visit re-pointing needs ``project.task.fm_contract_order_id``, and
that field is declared here. A post-migration in fm_contract runs while
fm_fsm is still unloaded, so the field would not exist yet.

Idempotent: a contract whose order already carries ``is_fm_contract`` is
skipped, and children/visits are only filled where the new link is empty.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Legacy field -> its fm_-prefixed twin on sale.order. The prefix exists
# because sale_project and sale_subscription already own several of these
# names on the order; see fm_contract/models/sale_order.py.
FIELD_MAP = {
    "contract_number": "fm_contract_number",
    "contract_type": "fm_contract_type",
    "service_line": "fm_service_line",
    "start_date": "fm_start_date",
    "end_date": "fm_end_date",
    "auto_renew": "fm_auto_renew",
    "renewal_term_months": "fm_renewal_term_months",
    "acv": "fm_acv",
    "billing_frequency": "fm_billing_frequency",
    "next_invoice_date": "fm_next_invoice_date",
    "health_score": "fm_health_score",
    "account_manager_id": "fm_account_manager_id",
    "asset_ids": "fm_asset_ids",
    "service_inclusions": "fm_service_inclusions",
    "service_exclusions": "fm_service_exclusions",
    "customer_contact_ids": "fm_customer_contact_ids",
}

# Same name on both sides: fm.contract and sale.order both inherit
# fm.agreement.mixin and fm.visit.schedule.mixin, so these need no mapping.
SHARED_FIELDS = (
    # fm.agreement.mixin — the printed wording
    "subject", "scope_notes", "treatment_notes", "payment_terms_note",
    "unscheduled_visits_included", "termination_notice_days",
    "complaint_response_hours", "agreement_template_id",
    "quotation_intro_text", "scope_method_text", "service_text",
    "schedule_text", "exclusions_text", "agreement_standalone",
    # fm.visit.schedule.mixin — the cadence, so the schedule keeps generating
    "auto_schedule", "visit_frequency", "custom_interval_days",
    "skip_weekends", "preferred_technician_id", "auto_schedule_state",
    "fm_time_slot", "visit_start_time", "visit_duration_hours",
)

# fm.contract.state -> sale.order.fm_lifecycle. draft and negotiating have
# no twin: fm_lifecycle deliberately starts where the order's own state
# stops, and stays blank until the order is confirmed.
STATE_TO_LIFECYCLE = {
    "active": "active",
    "renewal_pipeline": "renewal_pipeline",
    "expired": "expired",
    "terminated": "terminated",
}

# Every child already carries both links; only the order side needs filling.
CHILD_MODELS = (
    "fm.sla.rule",
    "fm.contract.penalty",
    "fm.contract.agreement.line",
)


def _copy_value(contract, source):
    """One field's value, in whichever form a write() needs it."""
    field = contract._fields[source]
    value = contract[source]
    if field.type in ("many2many", "one2many"):
        return [(6, 0, value.ids)]
    if field.type == "many2one":
        return value.id or False
    return value


def _contract_vals(contract, order):
    """Everything the legacy record knows, as one write.

    One write rather than a field at a time: most of these carry
    ``tracking=True``, so writing them separately would leave twenty-odd
    tracking lines in the order's chatter instead of a single entry.

    ``is_fm_contract`` goes in the same write as ``fm_contract_number``
    deliberately. sale.order.write() hands out a contract number when the
    flag is set and no number exists — including the number already in
    this dict means the legacy AMC number is kept and no sequence is burnt.
    """
    vals = {}
    for source, target in FIELD_MAP.items():
        if source in contract._fields and target in order._fields:
            vals[target] = _copy_value(contract, source)
    for name in SHARED_FIELDS:
        if name in contract._fields and name in order._fields:
            vals[name] = _copy_value(contract, name)
    if "fm_lifecycle" in order._fields:
        vals["fm_lifecycle"] = STATE_TO_LIFECYCLE.get(contract.state) or False
    vals["is_fm_contract"] = True
    return vals


def _repoint_children(env, contract, order):
    """Fill the order side of each child's two links.

    WARNING for whoever retires fm.contract next: all three of these carry
    ``contract_id = Many2one("fm.contract", ondelete="cascade")``. Deleting
    the fm.contract rows would therefore destroy these children *even
    though* this migration has just re-pointed them at the order — the
    order_id is set, but Postgres takes the row anyway. Clear contract_id
    on the migrated children (or drop the constraint) before deleting
    anything, or the SLA rules, penalties and agreement wording go with it.
    """
    moved = 0
    for model in CHILD_MODELS:
        if model not in env:
            continue
        Child = env[model]
        if "contract_id" not in Child._fields or "order_id" not in Child._fields:
            continue
        children = Child.search([
            ("contract_id", "=", contract.id),
            ("order_id", "=", False),
        ])
        if children:
            children.order_id = order.id
            moved += len(children)
    return moved


def _repoint_visits(env, contract, order):
    Task = env["project.task"]
    if "fm_contract_id" not in Task._fields or "fm_contract_order_id" not in Task._fields:
        return 0
    # fm_contract_id is left in place: the model is retired in a later
    # change, and keeping both links until then makes this reversible.
    tasks = Task.search([
        ("fm_contract_id", "=", contract.id),
        ("fm_contract_order_id", "=", False),
    ])
    if tasks:
        tasks.fm_contract_order_id = order.id
    return len(tasks)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "fm.contract" not in env:
        return
    Contract = env["fm.contract"]
    contracts = Contract.search([])
    if not contracts:
        _logger.info("No legacy fm.contract records to carry across.")
        return

    migrated = skipped = children = visits = 0
    for contract in contracts:
        order = contract.sale_order_id
        if not order:
            _logger.warning(
                "Legacy contract %s has no sale order; skipped.", contract.id)
            skipped += 1
            continue
        # The children and the visits are re-pointed whatever the order's
        # flag says. They are guarded on their own (only an empty order
        # link is filled), and an order somebody had already ticked by hand
        # would otherwise keep its visits stranded on the legacy link.
        children += _repoint_children(env, contract, order)
        visits += _repoint_visits(env, contract, order)
        if order.is_fm_contract:
            skipped += 1
            continue
        order.write(_contract_vals(contract, order))
        migrated += 1
        order.message_post(body=(
            "Carried across from the legacy contract record %s. The FM "
            "fields, SLA rules, penalties, agreement wording and visits now "
            "hang off this order, which is where contracts live."
        ) % (contract.contract_number or contract.id))

    _logger.info(
        "Legacy contracts carried onto their orders: %s migrated, %s skipped, "
        "%s child record(s) re-pointed, %s visit(s) linked.",
        migrated, skipped, children, visits)
