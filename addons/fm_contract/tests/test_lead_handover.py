# -*- coding: utf-8 -*-
"""The CRM -> Sales -> Accounts -> Operations handover.

The rule that matters is the gate: the client's process document says
Operations confirmation is "allowed only after Accounts confirmation", so
most of these tests are about the ways someone might get past it.
"""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLeadHandover(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lead = cls.env["crm.lead"].create({"name": "Marina Heights AMC"})

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------
    def test_operations_cannot_confirm_before_accounts(self):
        self.lead.action_fm_sales_qualify()
        with self.assertRaises(ValidationError):
            self.lead.action_fm_ops_confirm()
        self.assertFalse(self.lead.fm_ops_confirmed_date)

    def test_operations_can_confirm_once_accounts_has(self):
        self.lead.action_fm_sales_qualify()
        self.lead.action_fm_accounts_confirm()
        self.lead.action_fm_ops_confirm()
        self.assertTrue(self.lead.fm_ops_confirmed_date)

    def test_the_gate_survives_a_direct_write(self):
        """Bypassing the button must not bypass the rule.

        The button raises a friendly error; the constraint is what makes the
        rule true for imports, RPC and server actions.
        """
        with self.assertRaises(ValidationError):
            self.lead.write({
                "fm_ops_confirmed_date": "2026-09-19 08:00:00",
            })

    def test_accounts_confirmation_cannot_be_withdrawn_underneath(self):
        """Clearing the Accounts date would leave Operations confirmed on a
        lead Accounts never confirmed — the same broken state, reached from
        the other end."""
        self.lead.action_fm_sales_qualify()
        self.lead.action_fm_accounts_confirm()
        self.lead.action_fm_ops_confirm()
        with self.assertRaises(ValidationError):
            self.lead.fm_accounts_confirmed_date = False

    def test_confirming_twice_is_harmless(self):
        self.lead.action_fm_sales_qualify()
        self.lead.action_fm_accounts_confirm()
        first = self.lead.fm_accounts_confirmed_date
        self.lead.action_fm_accounts_confirm()
        self.assertEqual(self.lead.fm_accounts_confirmed_date, first)

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------
    def test_pipeline_stage_follows_the_handover(self):
        self.assertEqual(self.lead.fm_pipeline_stage, "lead")
        self.lead.action_fm_sales_qualify()
        self.assertEqual(self.lead.fm_pipeline_stage, "qualified")
        self.lead.action_fm_accounts_confirm()
        self.assertEqual(self.lead.fm_pipeline_stage, "accounts")
        self.lead.action_fm_ops_confirm()
        self.assertEqual(self.lead.fm_pipeline_stage, "operations")

    def test_each_step_records_who_and_when(self):
        """An approval nobody can be traced to is not an approval."""
        self.lead.action_fm_sales_qualify()
        self.lead.action_fm_accounts_confirm()
        self.lead.action_fm_ops_confirm()
        for date_field, uid_field in (
            ("fm_sales_qualified_date", "fm_sales_qualified_uid"),
            ("fm_accounts_confirmed_date", "fm_accounts_confirmed_uid"),
            ("fm_ops_confirmed_date", "fm_ops_confirmed_uid"),
        ):
            self.assertTrue(self.lead[date_field], date_field)
            self.assertEqual(self.lead[uid_field], self.env.user, uid_field)
