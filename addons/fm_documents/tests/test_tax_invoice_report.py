# -*- coding: utf-8 -*-
"""The FM Tax Invoice prints, and prints the right things.

Rendering is the only check worth having on a QWeb template. One naming a
field the model does not have loads perfectly happily and raises on the
first print -- so a ported document that has been read and looks right is
not evidence of anything. These tests render it.

They also pin the two properties that are easy to lose in a later edit and
expensive to lose in production: that the layout refuses to print for a
vendor bill, and that Odoo's own invoice report is left alone.
"""
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged

REPORT = "fm_documents.action_report_fm_tax_invoice"


@tagged("post_install", "-at_install")
class TestFmTaxInvoiceReport(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data["company"].write({
            "vat": "100123456700003",
            "company_registry": "CN-1234567",
        })
        cls.customer = cls.env["res.partner"].create({
            "name": "Royal Apartment Owners Association",
            "vat": "100987654300003",
            "street": "Abu Hail, Deira",
            "city": "Dubai",
        })
        cls.service = cls.env["product.product"].create({
            "name": "Quarterly Water Tank Cleaning",
            "default_code": "AAB-WTC-Q",
            "type": "service",
            "list_price": 1500.0,
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _render(self, move):
        report = self.env.ref(REPORT)
        html, _kind = report._render_qweb_html(REPORT, move.ids)
        return html.decode() if isinstance(html, bytes) else html

    def _invoice(self, move_type="out_invoice", post=True, **write):
        move = self.init_invoice(
            move_type, partner=self.customer, products=self.service,
            taxes=self.company_data["default_tax_sale"], post=post)
        if write:
            move.write(write)
        return move

    # ------------------------------------------------------------------
    # it prints
    # ------------------------------------------------------------------

    def test_a_posted_invoice_renders_with_the_mandatory_fta_fields(self):
        move = self._invoice()
        html = self._render(move)
        self.assertIn("Tax Invoice", html)
        self.assertIn(move.name, html)
        self.assertIn("Royal Apartment Owners Association", html)
        self.assertIn("100123456700003", html, "supplier TRN missing")
        self.assertIn("100987654300003", html, "recipient TRN missing")
        self.assertIn("CN-1234567", html, "trade licence missing")
        self.assertIn("Federal Decree-Law No. 8 of 2017", html)

    def test_a_credit_note_is_titled_as_one(self):
        """Not "Tax Invoice". A credit note headed as an invoice is a
        document the customer can file against the wrong return."""
        move = self._invoice("out_refund")
        html = self._render(move)
        self.assertIn("Tax Credit Note", html)

    def test_a_draft_invoice_still_prints(self):
        """Every optional block has to degrade: an invoice is printed for
        checking long before it is posted."""
        move = self._invoice(post=False)
        self.assertTrue(self._render(move))

    def test_the_arabic_title_is_on_the_page(self):
        """The other fm documents are bilingual; this one was not, on the
        build it came from. It is now."""
        html = self._render(self._invoice())
        self.assertIn("فاتورة ضريبية", html)

    # ------------------------------------------------------------------
    # it refuses to print the wrong thing
    # ------------------------------------------------------------------

    def test_a_vendor_bill_is_refused(self):
        """The Print binding is on account.move as a whole because Odoo
        cannot bind a report to a subset of a model. The guard is the only
        thing standing between that and a supplier invoice printed under a
        "Tax Invoice" heading."""
        bill = self._invoice("in_invoice")
        with self.assertRaises(UserError):
            self._render(bill)

    def test_odoos_own_invoice_report_is_untouched(self):
        """The failure this prevents took every sale order in a database
        out of action once: a module pointed a core report record at its
        own template, the template went away, and nothing printed."""
        native = self.env.ref("account.account_invoices")
        self.assertTrue(native.report_name.startswith("account."),
                        "Odoo's invoice report must still point into account")
        self.assertNotIn("fm_documents", native.report_name)
        ours = self.env.ref(REPORT)
        self.assertEqual(ours.model, "account.move")
        self.assertEqual(ours.report_name, "fm_documents.report_fm_tax_invoice")
        self.assertTrue(ours.binding_model_id,
                        "the Tax Invoice is meant to be in the Print menu")

    # ------------------------------------------------------------------
    # the details that are easy to get wrong
    # ------------------------------------------------------------------

    def test_the_internal_product_code_is_stripped_from_the_description(self):
        """'[AAB-WTC-Q] Quarterly ...' -- the code is ours, and a customer
        reading their invoice has no use for it."""
        move = self._invoice()
        line = move.invoice_line_ids[:1]
        line.name = "[AAB-WTC-Q] Quarterly Water Tank Cleaning"
        self.assertEqual(
            move._fm_line_description(line), "Quarterly Water Tank Cleaning")
        self.assertNotIn("[AAB-WTC-Q]", self._render(move))

    def test_sections_and_notes_are_not_numbered(self):
        """The line number is what a customer quotes back on the phone, so
        it counts chargeable lines only -- not the loop index."""
        move = self._invoice(post=False)
        move.write({"invoice_line_ids": [
            (0, 0, {"display_type": "line_section", "name": "Roof tanks"}),
            (0, 0, {"display_type": "line_note", "name": "Access via stair 2."}),
        ]})
        rows = move._fm_numbered_lines()
        numbered = [r["no"] for r in rows if r["no"] is not None]
        self.assertEqual(numbered, list(range(1, len(numbered) + 1)))
        for row in rows:
            if row["line"].display_type:
                self.assertIsNone(row["no"], row["line"].name)

    def test_the_total_is_spelled_out(self):
        move = self._invoice()
        self.assertTrue(move._fm_amount_in_words())
        self.assertIn(move._fm_amount_in_words(), self._render(move))

    def test_the_tax_breakdown_names_each_rate(self):
        move = self._invoice()
        breakdown = move._fm_tax_breakdown()
        self.assertTrue(breakdown, "an invoice with tax should break it down")
        for row in breakdown:
            self.assertIn(row["name"], self._render(move))

    def test_reverse_charge_is_not_claimed_by_default(self):
        """Telling a customer the VAT is theirs to account for when it is
        not is a tax error on a document they will file."""
        move = self._invoice()
        self.assertFalse(move._fm_reverse_charge())
        self.assertNotIn("reverse charge mechanism", self._render(move))

    def test_reverse_charge_is_claimed_when_the_fiscal_position_says_so(self):
        position = self.env["account.fiscal.position"].create({
            "name": "UAE Reverse Charge",
            "company_id": self.company_data["company"].id,
        })
        move = self._invoice(post=False, fiscal_position_id=position.id)
        self.assertTrue(move._fm_reverse_charge())
        self.assertIn("reverse charge mechanism", self._render(move))

    def test_bank_details_appear_only_when_there_is_a_bank_account(self):
        """Details a customer is asked to pay into are never invented to
        fill a gap in the layout."""
        company = self.company_data["company"]
        company.partner_id.bank_ids.unlink()
        move = self._invoice()
        self.assertNotIn("Payment Details", self._render(move))

        self.env["res.partner.bank"].create({
            "acc_number": "AE070331234567890123456",
            "partner_id": company.partner_id.id,
            "acc_holder_name": "Aabaan Services",
        })
        self.env.invalidate_all()
        html = self._render(move)
        self.assertIn("Payment Details", html)
        self.assertIn("AE070331234567890123456", html)

    # ------------------------------------------------------------------
    # Document Audit Trail
    # ------------------------------------------------------------------

    def test_the_audit_trail_says_nothing_before_the_invoice_is_posted(self):
        move = self._invoice(post=False)
        self.assertIn("audit trail starts once this document is posted",
                      move.fm_audit_trail_html)

    def test_the_audit_trail_records_creation_and_posting(self):
        move = self._invoice()
        labels = [row["label"] for row in move._fm_audit_trail()]
        self.assertIn("Created", labels)
        self.assertIn("Posted", labels)
        self.assertIn("<table", move.fm_audit_trail_html)

    def test_the_audit_trail_claims_nothing_that_has_not_happened(self):
        """A milestone that has not happened does not appear. An invented
        date on a document a customer may dispute is worse than a gap."""
        move = self._invoice()
        labels = [row["label"] for row in move._fm_audit_trail()]
        self.assertNotIn("Sent to customer", labels)
        self.assertNotIn("Payment received", labels)

    def test_a_vendor_bill_has_no_audit_trail(self):
        bill = self._invoice("in_invoice")
        self.assertFalse(bill.fm_audit_trail_html)
