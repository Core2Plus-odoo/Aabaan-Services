# -*- coding: utf-8 -*-
"""The Service Agreement and the Quotation print from the sale order.

These two PDFs are the documents the customer signs, and they used to be
bound to fm.contract -- a model nothing creates any more. Everything a
salesperson typed into the order's "Printed Agreement" tab therefore had
nowhere to come out.

Rendering is the only check worth having here. A QWeb template naming a
field that does not exist on the model loads perfectly happily and then
raises on the first print, so nothing short of actually rendering it
catches a missed rename -- which is exactly what moving these templates
from fm.contract's field names to the order's was.
"""
from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestContractReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contact = cls.env["res.partner"].create({
            "name": "Mr. Site Manager", "phone": "055 859 8834",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Royal Apartment Owners Association",
            "child_ids": [(4, cls.contact.id)],
        })
        cls.product = cls.env["product.product"].create({
            "name": "Quarterly Water Tank Cleaning",
            "type": "service",
            "list_price": 1500.0,
        })
        Item = cls.env["fm.contract.service.item"]
        cls.inclusion = Item.create({"name": "Quarterly tank disinfection"})
        cls.exclusion = Item.create({"name": "Structural tank repair"})

    def _contract(self, **extra):
        """An FM contract with every block the two templates can render
        populated -- inclusions, exclusions, contacts, SLA rules and an
        extra article each drive a branch of the QWeb."""
        vals = {
            "partner_id": self.partner.id,
            "is_fm_contract": True,
            "fm_contract_number": "AMC-TEST-0001",
            "fm_start_date": date(2026, 1, 1),
            "fm_end_date": date(2026, 12, 31),
            "validity_date": date.today() + timedelta(days=30),
            "subject": "WATER TANK CLEANING FOR ROYAL APARTMENT G+11",
            "scope_notes": "All 6 roof tanks and the 2 underground tanks.",
            "treatment_notes": "Drain, scrub, chlorinate, flush, lab-test.",
            "payment_terms_note": "50% at signing, 50% after 6 months.",
            "unscheduled_visits_included": 2,
            "termination_notice_days": 30,
            "complaint_response_hours": 24,
            "fm_service_inclusions": [(6, 0, self.inclusion.ids)],
            "fm_service_exclusions": [(6, 0, self.exclusion.ids)],
            "fm_customer_contact_ids": [(6, 0, self.contact.ids)],
            "fm_sla_rule_ids": [(0, 0, {
                "name": "Water contamination report",
                "severity": "p1_critical",
                "response_target_minutes": 60,
                "resolution_target_minutes": 480,
            })],
            "agreement_line_ids": [(0, 0, {
                "name": "Tank Details",
                "body": "6 x 1,000 gallon GRP roof tanks.",
            })],
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 4,
                "price_unit": 1500.0,
            })],
        }
        vals.update(extra)
        return self.env["sale.order"].create(vals)

    def _render(self, xmlid, order):
        report = self.env.ref(xmlid)
        html, _content_type = report._render_qweb_html(xmlid, order.ids)
        return html.decode() if isinstance(html, bytes) else html

    def test_service_agreement_renders_from_the_order(self):
        order = self._contract()
        html = self._render("fm_documents.action_report_fm_contract", order)
        self.assertIn("AMC-TEST-0001", html)
        self.assertIn("Royal Apartment Owners Association", html)
        self.assertIn("Quarterly tank disinfection", html)
        self.assertIn("Structural tank repair", html)
        self.assertIn("Water contamination report", html)
        self.assertIn("Tank Details", html)

    def test_quotation_renders_from_the_order(self):
        order = self._contract()
        html = self._render("fm_documents.action_report_fm_quotation", order)
        self.assertIn("AMC-TEST-0001", html)
        self.assertIn("Mr. Site Manager", html)
        self.assertIn("Quarterly tank disinfection", html)
        self.assertIn("Quarterly Water Tank Cleaning", html)

    # ------------------------------------------------------------------
    # Placeholders reach the page
    # ------------------------------------------------------------------
    def test_placeholders_are_filled_in_on_the_printed_agreement(self):
        """The whole point of the engine: wording written once with a
        placeholder comes out of the printer with the contract's own
        facts in it.

        Rendered rather than unit-tested, because a wording field wired
        to the page without the renderer looks identical in the form and
        only shows up as a raw {{CLIENT}} on a customer's document.
        """
        order = self._contract(service_text="Prepared for {{CLIENT}}.")
        html = self._render("fm_documents.action_report_fm_contract", order)
        self.assertIn("Prepared for Royal Apartment Owners Association.", html)
        self.assertNotIn("{{CLIENT}}", html)

    def test_placeholders_are_filled_in_on_the_quotation(self):
        order = self._contract(quotation_intro_text="For {{CLIENT}}, {{VISITS}} visits.")
        html = self._render("fm_documents.action_report_fm_quotation", order)
        self.assertIn("Royal Apartment Owners Association", html)
        self.assertNotIn("{{CLIENT}}", html)
        self.assertNotIn("{{VISITS}}", html)

    def test_an_additional_article_is_filled_in_too(self):
        """Article bodies are rendered inside a t-foreach, which is the
        site most easily missed -- the loop variable is not the order."""
        order = self._contract(agreement_line_ids=[(0, 0, {
            "name": "Site", "body": "Work is carried out for {{CLIENT}}.",
        })])
        for xmlid in ("fm_documents.action_report_fm_contract",
                      "fm_documents.action_report_fm_quotation"):
            html = self._render(xmlid, order)
            self.assertNotIn("{{CLIENT}}", html, xmlid)

    def test_a_fact_the_contract_cannot_supply_prints_a_pencil_mark(self):
        """Not a blank. A blank on a signature page is how a missing
        licence reaches a customer; a pencil mark is visibly wrong where
        somebody proofreading will catch it."""
        order = self._contract(service_text="Licence: {{LICENCE}}")
        html = self._render("fm_documents.action_report_fm_contract", order)
        self.assertIn("\u270e", html)
        self.assertNotIn("{{LICENCE}}", html)

    def test_wording_with_no_placeholders_prints_unchanged(self):
        """The renderer sits on every wording field now, so ordinary
        prose must pass through it untouched."""
        order = self._contract(service_text="Plain wording, no placeholders.")
        html = self._render("fm_documents.action_report_fm_contract", order)
        self.assertIn("Plain wording, no placeholders.", html)

    def test_both_reports_target_the_order(self):
        """Not fm.contract. The binding is cleared too: left pointing at
        fm.contract it would cascade-delete these actions when that model
        is dropped."""
        for xmlid in ("fm_documents.action_report_fm_contract",
                      "fm_documents.action_report_fm_quotation"):
            report = self.env.ref(xmlid)
            self.assertEqual(report.model, "sale.order", xmlid)
            self.assertFalse(report.binding_model_id, xmlid)

    def test_an_empty_contract_still_prints(self):
        """Nothing filled in but the flag -- every optional block has to
        degrade, because a quotation is printed before it is complete."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_fm_contract": True,
        })
        for xmlid in ("fm_documents.action_report_fm_contract",
                      "fm_documents.action_report_fm_quotation"):
            self.assertTrue(self._render(xmlid, order))
