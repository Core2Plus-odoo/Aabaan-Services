# -*- coding: utf-8 -*-
from odoo import models
from odoo.fields import Domain

# The Command Centre's branch filter. While a tab is computed for one branch
# its environment carries this key, and every search on the models below
# gets that branch's domain added -- every figure, batched _read_group,
# search_count and sub-query alike -- so no query in the provider has to
# remember to filter, and none can forget to.
#
# Gated on the context key alone: anywhere else in Odoo the key is absent
# and these searches are untouched.
CONTEXT_KEY = "fm_cc_branch_id"


def _scoped(records, domain):
    branch_id = records.env.context.get(CONTEXT_KEY)
    if not branch_id:
        return domain
    fragment = records.env["fm.command.centre"]._branch_fragment(records._name, branch_id)
    if fragment is None:
        return domain
    return Domain(domain) & Domain(fragment)


# One plain _inherit per model, sharing the body through _scoped(): a plain
# Python class mixed into the bases breaks the registry (CLAUDE.md, §4).
class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _search(self, domain, *args, **kwargs):
        return super()._search(_scoped(self, domain), *args, **kwargs)


class ProjectTask(models.Model):
    _inherit = "project.task"

    def _search(self, domain, *args, **kwargs):
        return super()._search(_scoped(self, domain), *args, **kwargs)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _search(self, domain, *args, **kwargs):
        return super()._search(_scoped(self, domain), *args, **kwargs)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _search(self, domain, *args, **kwargs):
        return super()._search(_scoped(self, domain), *args, **kwargs)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _search(self, domain, *args, **kwargs):
        return super()._search(_scoped(self, domain), *args, **kwargs)
