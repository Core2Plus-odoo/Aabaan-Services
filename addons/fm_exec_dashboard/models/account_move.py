# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    """Branch on the invoice, so money can be reported per emirate.

    Revenue already knows its branch: a customer invoice comes from a sale
    order, and ``sale.order.branch_id`` has carried the branch since the
    contract was written. This field follows that link and stores it, which
    is what lets the dashboard group revenue, receivables and spend by city
    without walking back through the order on every read.

    A plain field filled on create and on post, rather than a computed one:
    a computed-but-writable field would have to read its own current value
    to know whether a person had already chosen a branch, and reading a
    stored computed field inside its own compute is how recursion bugs
    start. Create and post are the two moments the value is needed, and
    both are explicit.

    Nothing overwrites a branch already set. A vendor bill has no sale order
    behind it — office rent for the Dubai branch is something a person has
    to say — and once said, it stands.
    """

    _inherit = "account.move"

    branch_id = fields.Many2one(
        "fm.branch",
        string="Branch",
        index=True,
        tracking=True,
        help="The Aabaan branch this document belongs to. Filled from the "
             "source sale order on a customer invoice; set it by hand on a "
             "vendor bill or journal entry so the cost lands in the right "
             "branch's numbers. Spend with no branch is reported as "
             "unallocated on the CEO dashboard rather than spread across "
             "branches.",
    )

    def _fm_derive_branch(self):
        """The branch of the sale order behind this invoice, if there is one."""
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund"):
            return self.env["fm.branch"]
        if "sale_line_ids" not in self.env["account.move.line"]._fields:
            return self.env["fm.branch"]
        orders = self.invoice_line_ids.sale_line_ids.order_id
        if not orders or "branch_id" not in orders._fields:
            return self.env["fm.branch"]
        return orders[:1].branch_id

    def _fm_fill_branch(self):
        """Fill the branch where it is blank and derivable. Never overwrite."""
        for move in self:
            if move.branch_id:
                continue
            branch = move._fm_derive_branch()
            if branch:
                move.branch_id = branch.id

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._fm_fill_branch()
        return moves

    def _post(self, soft=True):
        # Second chance: an invoice whose lines were attached after create
        # still gets its branch before the figures start counting it.
        self._fm_fill_branch()
        return super()._post(soft=soft)
