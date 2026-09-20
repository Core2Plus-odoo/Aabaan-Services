# -*- coding: utf-8 -*-
"""The standard Quotation / Order PDF prints.

It did not. sale.action_report_saleorder carried a leftover redirect to
``aabaan_quotation_report.report_saleorder_aabaan`` -- a template from the
other Odoo.sh project, whose addons this build does not load -- so every
sale order in the database raised "Template not found" on print, on Send
by email and on the customer portal.

The action belongs to ``sale``, not to the module that redirected it,
which is why nothing restored it when that module went: the template was
deleted with the module and the core action was left pointing at the
hole. Rendering is the test, because a report action naming a template
that does not exist looks perfectly healthy in the database and only
fails when someone presses Print in front of a customer.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleReportRepair(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Quotation Print Test"})
        cls.product = cls.env["product.product"].create({
            "name": "Ad-hoc Cleaning Visit",
            "type": "service",
            "list_price": 750.0,
        })

    def test_the_core_action_points_at_odoos_own_template(self):
        report = self.env.ref("sale.action_report_saleorder")
        self.assertEqual(report.report_name, "sale.report_saleorder")
        self.assertEqual(report.report_file, "sale.report_saleorder")

    def test_an_ordinary_quotation_prints(self):
        """Not an FM contract -- the plain sales document every customer
        gets, which is what was broken."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 750.0,
            })],
        })
        html, _content_type = self.env["ir.actions.report"]._render_qweb_html(
            "sale.action_report_saleorder", order.ids
        )
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn(order.name, html)
        self.assertIn("Ad-hoc Cleaning Visit", html)

    def test_an_fm_contract_also_prints_the_standard_document(self):
        """The FM Service Agreement and FM Quotation are separate actions
        on their own buttons; ticking a contract must not cost it the
        standard sales document."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_fm_contract": True,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 750.0,
            })],
        })
        html, _content_type = self.env["ir.actions.report"]._render_qweb_html(
            "sale.action_report_saleorder", order.ids
        )
        self.assertTrue(html)
