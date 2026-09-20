# -*- coding: utf-8 -*-
"""Agreement wording written once, filled in per contract.

Written against fm_branch because it loads last and is the only place
that can see the whole chain: fm_contract supplies the dates and terms,
fm_fsm the visit count, fm_branch the licence. A test in any earlier
module would pass while a later contributor silently did nothing.

That "silently" is the point. Each module contributes by overriding
_fm_agreement_placeholder_values on sale.order rather than by extending
fm.agreement.mixin, because extending an AbstractModel only reaches the
concrete models built before the extension is registered -- and
sale.order was composed back in fm_contract. The mixin version would
load cleanly and never run. These tests are what would catch that.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAgreementPlaceholders(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Royal Apartments LLC",
            "street": "Al Nahda Street",
            "city": "Sharjah",
        })
        cls.licensed = cls.env["fm.branch"].create({
            "name": "Dubai Licensed Branch", "emirate": "dubai",
            "licence_number": "989-TEST",
        })
        cls.unlicensed = cls.env["fm.branch"].create({
            "name": "Fujairah Branch", "emirate": "fujairah",
        })

    def _contract(self, **extra):
        vals = {"partner_id": self.partner.id, "is_fm_contract": True}
        vals.update(extra)
        return self.env["sale.order"].create(vals)

    # ------------------------------------------------------------------
    # Each module contributes what it can see
    # ------------------------------------------------------------------
    def test_every_module_contributes_its_own_facts(self):
        """The whole chain in one assertion: if any module's override
        stopped running, exactly one of these keys would go missing."""
        order = self._contract(
            branch_id=self.licensed.id,
            visit_frequency="monthly",
            fm_callout_allowance=2,
            fm_warranty_years=10,
            fm_complaint_sla="same_day",
        )
        values = order._fm_agreement_placeholder_values()
        self.assertEqual(values["CLIENT"], "Royal Apartments LLC")   # fm_contract
        self.assertEqual(values["CALLOUTS"], 2)                      # fm_contract
        self.assertEqual(values["VISITS"], 12)                       # fm_fsm
        self.assertEqual(values["LICENCE"], "989-TEST")              # fm_branch
        self.assertIn("Al Nahda Street", values["SITE"])
        self.assertEqual(values["SLA"], "Same day")

    def test_a_custom_cadence_is_counted_not_looked_up(self):
        order = self._contract(visit_frequency="custom", custom_interval_days=30)
        self.assertEqual(order._fm_agreement_placeholder_values()["VISITS"], 12)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def test_wording_is_filled_in(self):
        order = self._contract(branch_id=self.licensed.id, visit_frequency="quarterly")
        rendered = order._fm_render_agreement_text(
            "{{CLIENT}} receives {{VISITS}} visits a year under licence {{LICENCE}}."
        )
        self.assertEqual(
            rendered,
            "Royal Apartments LLC receives 4 visits a year under licence 989-TEST.",
        )

    def test_spacing_inside_the_braces_is_tolerated(self):
        order = self._contract()
        self.assertEqual(
            order._fm_render_agreement_text("Hello {{ CLIENT }}"),
            "Hello Royal Apartments LLC",
        )

    def test_a_missing_fact_prints_a_pencil_mark_not_a_blank(self):
        """A blank on a signature page is how a missing licence reaches a
        customer. A pencil mark is visibly wrong on the page, where
        somebody proofreading will catch it."""
        order = self._contract(branch_id=self.unlicensed.id)
        rendered = order._fm_render_agreement_text("Licence: {{LICENCE}}")
        self.assertIn("✎", rendered)
        self.assertIn("operating licence", rendered)
        self.assertNotEqual(rendered, "Licence: ")

    def test_an_unknown_placeholder_is_left_alone(self):
        """A typo should look like a typo, not like a fact nobody
        filled in."""
        order = self._contract()
        self.assertEqual(
            order._fm_render_agreement_text("See {{CLEINT}}"), "See {{CLEINT}}",
        )

    def test_lowercase_is_not_a_placeholder(self):
        order = self._contract()
        self.assertEqual(
            order._fm_render_agreement_text("a {{client}} b"), "a {{client}} b",
        )

    def test_rendering_never_writes(self):
        """The stored wording keeps its placeholders. That is what makes a
        licence filled in next week simply correct, with nothing to
        rebuild and no edit at risk -- the thing the Studio engine needed
        a 'lock terms' flag to work around."""
        order = self._contract(branch_id=self.unlicensed.id)
        order.service_text = "Licence {{LICENCE}}"
        order._fm_render_agreement_text(order.service_text)
        self.assertEqual(order.service_text, "Licence {{LICENCE}}")
        self.unlicensed.licence_number = "103-TEST"
        order.invalidate_recordset()
        self.assertEqual(
            order._fm_render_agreement_text(order.service_text), "Licence 103-TEST",
        )

    # ------------------------------------------------------------------
    # Counting what is missing
    # ------------------------------------------------------------------
    def test_the_count_names_only_what_the_wording_actually_uses(self):
        """A contract with no licence is not incomplete unless its
        wording asks for one."""
        order = self._contract(branch_id=self.unlicensed.id)
        order.service_text = "Nothing is required here."
        self.assertEqual(order.fm_agreement_unresolved_count, 0)
        order.service_text = "Licence {{LICENCE}}"
        self.assertEqual(order.fm_agreement_unresolved_count, 1)
        self.assertIn("licence", order.fm_agreement_unresolved_names)

    def test_a_placeholder_used_twice_is_one_missing_fact(self):
        order = self._contract(branch_id=self.unlicensed.id)
        order.service_text = "{{LICENCE}} and again {{LICENCE}}"
        order.schedule_text = "and once more {{LICENCE}}"
        self.assertEqual(order.fm_agreement_unresolved_count, 1)

    def test_additional_articles_are_scanned_too(self):
        """agreement_line_ids is declared on sale.order, not the mixin, so
        it is scanned by an override there. Easy to lose."""
        order = self._contract(branch_id=self.unlicensed.id)
        order.service_text = "Nothing here."
        order.agreement_line_ids = [(0, 0, {
            "sequence": 1, "name": "Warranty", "body": "Licence {{LICENCE}}",
        })]
        self.assertEqual(order.fm_agreement_unresolved_count, 1)

    def test_filling_the_fact_clears_the_count(self):
        order = self._contract(branch_id=self.unlicensed.id)
        order.service_text = "Licence {{LICENCE}}"
        self.assertEqual(order.fm_agreement_unresolved_count, 1)
        self.unlicensed.licence_number = "103-TEST"
        order.invalidate_recordset()
        self.assertEqual(order.fm_agreement_unresolved_count, 0)
        self.assertFalse(order.fm_agreement_unresolved_names)

    def test_wording_with_no_placeholders_is_returned_unchanged(self):
        order = self._contract()
        text = "The First Party agrees to supply the services described below."
        self.assertEqual(order._fm_render_agreement_text(text), text)

    def test_empty_wording_is_safe(self):
        order = self._contract()
        self.assertFalse(order._fm_render_agreement_text(""))
        self.assertFalse(order._fm_render_agreement_text(False))

    def test_a_quotation_with_no_customer_renders(self):
        """Wording is often written before anyone is on the order. An
        empty partner must not raise inside _display_address -- which
        would surface on a print, not on a save."""
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        order.partner_id = False
        order.partner_shipping_id = False
        self.assertIn("✎", order._fm_render_agreement_text("Site: {{SITE}}"))
